"""
Workflow Management API Routes
"""
from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel

from langtrader_api.dependencies import APIKey, WorkflowRepo, DbSession
from langtrader_api.schemas.base import APIResponse

router = APIRouter(prefix="/workflows", tags=["Workflows"])


# ========== Request Schemas ==========

class NodeUpdateRequest(BaseModel):
    name: str
    plugin_name: str
    display_name: Optional[str] = None
    enabled: bool = True
    execution_order: int
    config: Optional[dict] = None  # 节点配置（JSON对象）


class EdgeUpdateRequest(BaseModel):
    from_node: str
    to_node: str
    condition: Optional[str] = None


class WorkflowUpdateRequest(BaseModel):
    nodes: List[NodeUpdateRequest]
    edges: List[EdgeUpdateRequest]


class WorkflowCreateRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: str = "trading"


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


@router.get("/plugins", response_model=APIResponse[list])
async def list_available_plugins(
    api_key: APIKey,
):
    """
    List all available plugins (discovered from codebase)
    
    Note: This route must be defined BEFORE /{workflow_id} to avoid route conflicts
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
        "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
        "nodes": [],
        "edges": [],
    }
    
    # Get plugin metadata for enriching node info
    from langtrader_core.plugins.registry import registry
    registry.discover_plugins("langtrader_core.graph.nodes")
    plugin_metadata_map = {m.name: m for m in registry.list_plugins()}
    
    # Add nodes with plugin metadata
    if workflow.nodes:
        for node in sorted(workflow.nodes, key=lambda n: n.execution_order):
            plugin_meta = plugin_metadata_map.get(node.plugin_name)
            # 获取节点配置
            config = workflow_repo.get_node_config_dict(node.id)
            result["nodes"].append({
                "id": node.id,
                "name": node.name,
                "plugin_name": node.plugin_name,
                "display_name": node.display_name or (plugin_meta.display_name if plugin_meta else node.name),
                "description": plugin_meta.description if plugin_meta else None,
                "enabled": node.enabled,
                "execution_order": node.execution_order,
                "category": plugin_meta.category if plugin_meta else "general",
                "requires_llm": plugin_meta.requires_llm if plugin_meta else False,
                "requires_trader": plugin_meta.requires_trader if plugin_meta else False,
                "config": config,  # 包含节点配置
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


@router.put("/{workflow_id}", response_model=APIResponse[dict])
async def update_workflow(
    workflow_id: int,
    request: WorkflowUpdateRequest,
    api_key: APIKey,
    workflow_repo: WorkflowRepo,
    db: DbSession,
):
    """
    Update workflow nodes and edges (full replacement)
    
    This endpoint replaces all existing nodes and edges with the provided ones.
    Used by the visual workflow editor.
    """
    from langtrader_core.data.models.workflow import WorkflowNode, WorkflowEdge
    from datetime import datetime
    
    workflow = workflow_repo.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with id {workflow_id} not found"
        )
    
    try:
        # 1. 清空现有节点和边
        workflow_repo.clear_nodes_and_edges(workflow_id)
        
        # 2. 创建新节点并保存配置
        for node_data in request.nodes:
            new_node = WorkflowNode(
                workflow_id=workflow_id,
                name=node_data.name,
                plugin_name= node_data.plugin_name,
                display_name=node_data.display_name,
                enabled=node_data.enabled,
                execution_order=node_data.execution_order,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(new_node)
            db.flush()  # 获取节点ID
            
            # 保存节点配置（如果提供）
            if node_data.config:
                for key, value in node_data.config.items():
                    workflow_repo.set_node_config(new_node.id, key, value)
        
        # 3. 创建新边
        for edge_data in request.edges:
            new_edge = WorkflowEdge(
                workflow_id=workflow_id,
                from_node=edge_data.from_node,
                to_node=edge_data.to_node,
                condition=edge_data.condition,
                created_at=datetime.now(),
            )
            db.add(new_edge)
        
        # 4. 更新工作流的更新时间
        workflow.updated_at = datetime.now()
        db.add(workflow)
        
        db.commit()
        
        return APIResponse(
            data={
                "workflow_id": workflow_id,
                "nodes_count": len(request.nodes),
                "edges_count": len(request.edges),
            },
            message="Workflow updated successfully"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update workflow: {str(e)}"
        )


@router.post("", response_model=APIResponse[dict], status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: WorkflowCreateRequest,
    api_key: APIKey,
    db: DbSession,
):
    """
    Create a new workflow
    """
    from langtrader_core.data.models.workflow import Workflow
    from sqlmodel import select
    from datetime import datetime
    
    # 检查名称是否已存在
    statement = select(Workflow).where(Workflow.name == request.name)
    existing = db.exec(statement).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow with name '{request.name}' already exists"
        )
    
    # 创建新工作流
    new_workflow = Workflow(
        name=request.name,
        display_name=request.display_name or request.name,
        description=request.description,
        category=request.category,
        version="1.0.0",
        is_active=True,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    
    db.add(new_workflow)
    db.commit()
    db.refresh(new_workflow)
    
    return APIResponse(
        data={
            "id": new_workflow.id,
            "name": new_workflow.name,
            "display_name": new_workflow.display_name,
        },
        message="Workflow created successfully"
    )


@router.delete("/{workflow_id}", response_model=APIResponse[dict])
async def delete_workflow(
    workflow_id: int,
    api_key: APIKey,
    workflow_repo: WorkflowRepo,
    db: DbSession,
):
    """
    Delete a workflow and all its nodes/edges
    """
    workflow = workflow_repo.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow with id {workflow_id} not found"
        )
    
    try:
        # 清空节点和边
        workflow_repo.clear_nodes_and_edges(workflow_id)
        
        # 删除工作流
        db.delete(workflow)
        db.commit()
        
        return APIResponse(
            data={"workflow_id": workflow_id},
            message="Workflow deleted successfully"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete workflow: {str(e)}"
        )

