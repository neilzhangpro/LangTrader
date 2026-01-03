"""
Workflow Management API Routes
"""
from fastapi import APIRouter, HTTPException, status
from typing import List

from langtrader_api.dependencies import APIKey, WorkflowRepo
from langtrader_api.schemas.base import APIResponse

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.get("", response_model=APIResponse[list])
async def list_workflows(
    api_key: APIKey,
    workflow_repo: WorkflowRepo,
):
    """
    List all available workflows
    """
    from sqlmodel import select
    from langtrader_core.data.models.workflow import Workflow
    
    statement = select(Workflow)
    workflows = workflow_repo.session.exec(statement).all()
    
    result = []
    for w in workflows:
        result.append({
            "id": w.id,
            "name": w.name,
            "display_name": w.display_name,
            "version": w.version,
            "category": w.category,
            "is_active": w.is_active,
            "nodes_count": len(w.nodes) if w.nodes else 0,
            "edges_count": len(w.edges) if w.edges else 0,
        })
    
    return APIResponse(data=result)


@router.get("/{workflow_id}", response_model=APIResponse[dict])
async def get_workflow(
    workflow_id: int,
    api_key: APIKey,
    workflow_repo: WorkflowRepo,
):
    """
    Get workflow details including nodes and edges
    """
    workflow = workflow_repo.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with id {workflow_id} not found"
        )
    
    # Build response
    result = {
        "id": workflow.id,
        "name": workflow.name,
        "display_name": workflow.display_name,
        "description": workflow.description,
        "version": workflow.version,
        "category": workflow.category,
        "is_active": workflow.is_active,
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
        "nodes": [],
        "edges": [],
    }
    
    # Add nodes
    if workflow.nodes:
        for node in sorted(workflow.nodes, key=lambda n: n.execution_order):
            result["nodes"].append({
                "id": node.id,
                "name": node.name,
                "plugin_name": node.plugin_name,
                "display_name": node.display_name,
                "enabled": node.enabled,
                "execution_order": node.execution_order,
            })
    
    # Add edges
    if workflow.edges:
        for edge in workflow.edges:
            result["edges"].append({
                "id": edge.id,
                "from_node": edge.from_node,
                "to_node": edge.to_node,
                "condition": edge.condition,
            })
    
    return APIResponse(data=result)


@router.get("/{workflow_id}/nodes", response_model=APIResponse[list])
async def get_workflow_nodes(
    workflow_id: int,
    api_key: APIKey,
    workflow_repo: WorkflowRepo,
):
    """
    Get all nodes for a workflow with their configurations
    """
    workflow = workflow_repo.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with id {workflow_id} not found"
        )
    
    nodes = []
    if workflow.nodes:
        for node in sorted(workflow.nodes, key=lambda n: n.execution_order):
            # Get node config
            config = workflow_repo.get_node_config_dict(node.id)
            
            nodes.append({
                "id": node.id,
                "name": node.name,
                "plugin_name": node.plugin_name,
                "display_name": node.display_name,
                "description": node.description,
                "enabled": node.enabled,
                "execution_order": node.execution_order,
                "config": config,
            })
    
    return APIResponse(data=nodes)


@router.get("/plugins", response_model=APIResponse[list])
async def list_available_plugins(
    api_key: APIKey,
):
    """
    List all available plugins (discovered from codebase)
    """
    from langtrader_core.plugins.registry import registry
    
    # Discover plugins if not already done
    registry.discover_plugins("langtrader_core.graph.nodes")
    
    plugins = registry.list_plugins()
    
    result = []
    for metadata in plugins:
        result.append({
            "name": metadata.name,
            "display_name": metadata.display_name,
            "version": metadata.version,
            "author": metadata.author,
            "description": metadata.description,
            "category": metadata.category,
            "requires_trader": metadata.requires_trader,
            "requires_llm": metadata.requires_llm,
            "insert_after": metadata.insert_after,
            "suggested_order": metadata.suggested_order,
        })
    
    return APIResponse(data=result)

