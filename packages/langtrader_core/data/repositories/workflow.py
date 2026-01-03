# packages/langtrader_core/data/repositories/workflow.py
from sqlmodel import select, Session
from langtrader_core.data.models.workflow import (
    Workflow, WorkflowNode, NodeConfig, WorkflowEdge
)
from typing import List, Optional, Dict, Any
from langtrader_core.utils import get_logger
from datetime import datetime

logger = get_logger("workflow_repository")


class WorkflowRepository:
    """Workflow 仓储"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_workflow(
        self,
        name: str,
        **kwargs
    ) -> Workflow:
        """创建 workflow"""
        workflow = Workflow(
            name=name,
            **kwargs
        )
        self.session.add(workflow)
        self.session.commit()
        self.session.refresh(workflow)
        
        logger.info(f"✅ Created workflow: {name}")
        return workflow
    
    def get_workflow(self, workflow_id: int) -> Optional[Workflow]:
        """获取 workflow（包含所有节点和配置）"""
        statement = (
            select(Workflow)
            .where(Workflow.id == workflow_id)
        )
        workflow = self.session.exec(statement).first()
        
        if workflow:
            # 预加载关系
            self.session.refresh(workflow)
            for node in workflow.nodes:
                self.session.refresh(node)
                # 预加载配置
                for config in node.configs:
                    pass
        
        return workflow
    
    def get_active_workflow_by_bot(self, bot_id: int) -> Optional[Workflow]:
        """获取 bot 的活跃 workflow"""
        statement = (
            select(Workflow)
            .where(Workflow.bot_id == bot_id)
            .where(Workflow.is_active == True)
            .where(Workflow.is_default == True)
        )
        return self.session.exec(statement).first()
    
    def add_node(
        self,
        workflow_id: int,
        name: str,
        plugin_name: str,
        config: Dict[str, Any] = None,
        **kwargs
    ) -> WorkflowNode:
        """添加节点"""
        node = WorkflowNode(
            workflow_id=workflow_id,
            name=name,
            plugin_name=plugin_name,
            **kwargs
        )
        self.session.add(node)
        self.session.commit()
        self.session.refresh(node)
        
        # 添加配置
        if config:
            for key, value in config.items():
                self.set_node_config(node.id, key, value)
        
        logger.info(f"✅ Added node: {name} to workflow {workflow_id}")
        return node
    
    def set_node_config(
        self,
        node_id: int,
        key: str,
        value: Any,
        description: str = None
    ):
        """设置节点配置"""
        # 查找是否已存在
        statement = (
            select(NodeConfig)
            .where(NodeConfig.node_id == node_id)
            .where(NodeConfig.config_key == key)
        )
        config = self.session.exec(statement).first()
        
        if config:
            # 更新
            config.set_value(value)
            config.updated_at = datetime.now()
        else:
            # 创建
            config = NodeConfig(
                node_id=node_id,
                config_key=key,
                description=description
            )
            config.set_value(value)
            self.session.add(config)
        
        self.session.commit()
        logger.debug(f"✅ Set config: {key} = {value} for node {node_id}")
    
    def get_node_config_dict(self, node_id: int) -> Dict[str, Any]:
        """获取节点的完整配置字典"""
        statement = (
            select(NodeConfig)
            .where(NodeConfig.node_id == node_id)
        )
        configs = self.session.exec(statement).all()
        
        return {
            config.config_key: config.get_value()
            for config in configs
        }
    
    def add_edge(
        self,
        workflow_id: int,
        from_node: str,
        to_node: str,
        condition: str = None
    ):
        """添加边"""
        edge = WorkflowEdge(
            workflow_id=workflow_id,
            from_node=from_node,
            to_node=to_node,
            condition=condition
        )
        self.session.add(edge)
        self.session.commit()
        
        logger.debug(f"✅ Added edge: {from_node} -> {to_node}")
    
    def clear_nodes_and_edges(self, workflow_id: int) -> tuple:
        """
        清空 workflow 的所有节点和边
        
        执行顺序（遵循外键约束）：
        1. 删除所有边
        2. 删除所有节点配置
        3. 删除所有节点
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            tuple: (deleted_nodes_count, deleted_edges_count)
        """
        deleted_nodes = 0
        deleted_edges = 0
        
        # 1. 删除该 workflow 的所有边
        edges_stmt = select(WorkflowEdge).where(WorkflowEdge.workflow_id == workflow_id)
        edges = self.session.exec(edges_stmt).all()
        for edge in edges:
            self.session.delete(edge)
            deleted_edges += 1
        
        # 2. 获取该 workflow 的所有节点
        nodes_stmt = select(WorkflowNode).where(WorkflowNode.workflow_id == workflow_id)
        nodes = self.session.exec(nodes_stmt).all()
        
        # 3. 删除每个节点的配置，然后删除节点
        for node in nodes:
            # 删除节点配置
            configs_stmt = select(NodeConfig).where(NodeConfig.node_id == node.id)
            configs = self.session.exec(configs_stmt).all()
            for config in configs:
                self.session.delete(config)
            
            # 删除节点
            self.session.delete(node)
            deleted_nodes += 1
        
        # 提交事务
        self.session.commit()
        
        logger.info(f"🧹 Cleared workflow {workflow_id}: {deleted_nodes} nodes, {deleted_edges} edges")
        return (deleted_nodes, deleted_edges)
    
    def export_to_dict(self, workflow_id: int) -> Dict[str, Any]:
        """导出 workflow 为字典（兼容 YAML 格式）"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return None
        
        return {
            "workflow": {
                "name": workflow.name,
                "version": workflow.version,
                "description": workflow.description
            },
            "global": {
                "enable_tracing": workflow.enable_tracing,
                "tracing_project": workflow.tracing_project,
                "max_concurrent_symbols": workflow.max_concurrent_symbols
            },
            "nodes": [
                {
                    "name": node.name,
                    "plugin": node.plugin_name,
                    "enabled": node.enabled,
                    "config": self.get_node_config_dict(node.id)
                }
                for node in sorted(workflow.nodes, key=lambda n: n.execution_order)
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "condition": edge.condition
                }
                for edge in workflow.edges
            ]
        }