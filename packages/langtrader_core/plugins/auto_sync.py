# packages/langtrader_core/plugins/auto_sync.py
"""
插件自动同步模块（全量重建模式）

每次同步时：
1. 清空该 workflow 的所有节点和边
2. 根据 registry 中发现的插件重新创建节点
3. 按 execution_order 创建边

这种方式确保数据库中的 workflow 配置始终与代码中的插件定义保持一致，
避免删除或重命名插件后出现"幽灵节点"问题。
"""
import threading
import uuid
from typing import Dict, Any
from sqlmodel import Session
from langtrader_core.plugins.registry import registry
from langtrader_core.data.repositories.workflow import WorkflowRepository
from langtrader_core.plugins.protocol import NodeMetadata
from langtrader_core.utils import get_logger

logger = get_logger("plugin_auto_sync")


class PluginAutoSync:
    """
    插件自动同步器（全量重建模式）
    
    每次同步时清空所有节点和边，然后根据 registry 中发现的插件重新创建。
    确保数据库配置与代码定义保持一致。
    """

    # class lock
    _local_locks = {}
    _lock_creation_lock = threading.Lock()
    
    def __init__(self, session: Session):
        self.session = session
        self.workflow_repo = WorkflowRepository(session)
        self.lock_owner = f"bot_{uuid.uuid4().hex[:8]}"
    
    @classmethod
    def _get_lock(cls, workflow_id: int) -> threading.Lock:
        """
        获取 workflow 锁（线程安全的单例模式）
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            该 workflow 专用的锁对象
        """
        if workflow_id not in cls._local_locks:
            with cls._lock_creation_lock:
                # 双重检查
                if workflow_id not in cls._local_locks:
                    cls._local_locks[workflow_id] = threading.Lock()
                    logger.debug(f"🔒 Created lock for workflow {workflow_id}")
        
        return cls._local_locks[workflow_id]
    
    def sync_if_needed(self, workflow_id: int) -> Dict[str, int]:
        """
        全量重建同步插件到数据库（线程安全）
        
        每次同步时：
        1. 清空该 workflow 的所有节点和边
        2. 根据 registry 中发现的插件重新创建节点
        3. 按 execution_order 创建边
        
        Args:
            workflow_id: 目标 workflow ID
            
        Returns:
            统计信息 {"cleared_nodes": 0, "cleared_edges": 0, "added": 0, "failed": 0, "edges_created": 0}
        """
        # 🔒 获取 workflow 级别的锁
        lock = self._get_lock(workflow_id)
        
        with lock:
            logger.debug(f"🔒 Acquired sync lock for workflow {workflow_id}")
            
            stats = {
                "cleared_nodes": 0, 
                "cleared_edges": 0, 
                "added": 0, 
                "failed": 0, 
                "edges_created": 0
            }
            
            try:
                # 获取工作流
                workflow = self.workflow_repo.get_workflow(workflow_id)
                if not workflow:
                    logger.warning(f"⚠️  Workflow {workflow_id} not found, skipping auto-sync")
                    return stats
                
                # 🔒 如果 workflow 已有节点，说明已配置过，跳过自动同步
                # 这样用户在前端手动编辑的 workflow 配置不会被覆盖
                if workflow.nodes and len(workflow.nodes) > 0:
                    logger.info(f"ℹ️  Workflow {workflow_id} already has {len(workflow.nodes)} nodes, skipping auto-sync")
                    return stats
                
                # 🧹 阶段1：清空所有节点和边（仅首次同步时执行）
                logger.info(f"🧹 Phase 1: Initializing empty workflow {workflow_id}...")
                cleared_nodes, cleared_edges = self.workflow_repo.clear_nodes_and_edges(workflow_id)
                stats["cleared_nodes"] = cleared_nodes
                stats["cleared_edges"] = cleared_edges
                logger.info(f"   Cleared {cleared_nodes} nodes, {cleared_edges} edges")
                
                # 获取需要自动注册的插件
                discovered_plugins = registry._metadata  # {name: NodeMetadata}
                auto_register_plugins = [
                    (name, metadata) 
                    for name, metadata in discovered_plugins.items() 
                    if metadata.auto_register
                ]
                
                if not auto_register_plugins:
                    logger.warning(f"⚠️  No auto-register plugins found")
                    return stats
                
                # 按 execution_order 排序
                auto_register_plugins.sort(
                    key=lambda x: x[1].suggested_order if x[1].suggested_order is not None else 999
                )
                
                # 🔧 阶段2：创建所有节点
                logger.info(f"🔧 Phase 2: Creating {len(auto_register_plugins)} nodes...")
                for plugin_name, metadata in auto_register_plugins:
                    try:
                        self._create_node_only(workflow_id, metadata)
                        stats["added"] += 1
                        logger.info(f"   ✅ Created node: {plugin_name} (order={metadata.suggested_order})")
                    except Exception as e:
                        stats["failed"] += 1
                        logger.error(f"   ❌ Failed to create node '{plugin_name}': {e}")
                
                # 🔗 阶段3：创建所有边
                if stats["added"] > 0:
                    logger.info(f"🔗 Phase 3: Creating edges...")
                    
                    # 检查是否有条件节点需要特殊处理
                    conditional_plugins = [
                        (name, meta) for name, meta in auto_register_plugins 
                        if meta.is_conditional and meta.conditional_routes
                    ]
                    
                    if conditional_plugins:
                        # 有条件节点，需要特殊处理
                        logger.info(f"   Found {len(conditional_plugins)} conditional nodes")
                        for plugin_name, metadata in conditional_plugins:
                            edges_count = self._create_conditional_edges(workflow_id, plugin_name, metadata)
                            stats["edges_created"] += edges_count
                        
                        # 为非条件节点创建线性边
                        edges_count = self._create_linear_edges_except_conditional(
                            workflow_id, 
                            [name for name, _ in conditional_plugins]
                        )
                        stats["edges_created"] += edges_count
                    else:
                        # 没有条件节点，创建完整的线性边
                        edges_count = self._create_initial_edges(workflow_id)
                        stats["edges_created"] += edges_count
                
                logger.info(f"✅ Full rebuild completed: {stats['added']} nodes, {stats['edges_created']} edges")
                
            except Exception as e:
                logger.error(f"❌ Auto-sync failed: {e}", exc_info=True)
                stats["failed"] += 1
            
            logger.debug(f"🔓 Released sync lock for workflow {workflow_id}")
            return stats
    
    def _create_node_only(self, workflow_id: int, metadata: NodeMetadata):
        """只创建节点，不创建边"""
        workflow = self.workflow_repo.get_workflow(workflow_id)
        
        # 计算执行顺序
        if metadata.suggested_order is not None:
            execution_order = metadata.suggested_order
        else:
            max_order = max([node.execution_order for node in workflow.nodes], default=0)
            execution_order = max_order + 1
        
        # 创建节点
        node = self.workflow_repo.add_node(
            workflow_id=workflow_id,
            name=metadata.name,
            plugin_name=metadata.name,
            enabled=True,
            execution_order=execution_order,
            config=metadata.default_config
        )
        
        logger.debug(f"   Created node: {node.name} (order={execution_order})")
    
    def _create_conditional_edges(self, workflow_id: int, node_name: str, metadata: NodeMetadata) -> int:
        """
        创建条件边
        
        Returns:
            创建的边数量
        """
        count = 0
        
        # 为每个条件路由创建边
        for condition_value, target_node in metadata.conditional_routes.items():
            try:
                self.workflow_repo.add_edge(
                    workflow_id=workflow_id,
                    from_node=node_name,
                    to_node=target_node,
                    condition=condition_value
                )
                logger.info(f"   ✅ Conditional edge: {node_name} -[{condition_value}]-> {target_node}")
                count += 1
            except Exception as e:
                logger.error(f"   ❌ Failed to create conditional edge: {e}")
        
        return count
    
    def _create_initial_edges(self, workflow_id: int) -> int:
        """
        为所有节点创建初始边
        基于 execution_order 创建线性流程: START -> node1 -> node2 -> ... -> END
        
        Returns:
            创建的边数量
        """
        workflow = self.workflow_repo.get_workflow(workflow_id)
        count = 0
        
        # 获取所有节点，按 execution_order 排序
        sorted_nodes = sorted(workflow.nodes, key=lambda n: n.execution_order)
        
        if len(sorted_nodes) == 0:
            logger.warning("   No nodes to connect")
            return 0
        
        logger.info(f"   Creating initial edges for {len(sorted_nodes)} nodes...")
        
        # START -> first_node
        try:
            self.workflow_repo.add_edge(workflow_id, 'START', sorted_nodes[0].name)
            count += 1
            logger.info(f"   Created edge: START -> {sorted_nodes[0].name}")
        except Exception as e:
            logger.debug(f"   Edge START -> {sorted_nodes[0].name} may already exist: {e}")
        
        # node[i] -> node[i+1]
        for i in range(len(sorted_nodes) - 1):
            try:
                self.workflow_repo.add_edge(
                    workflow_id, 
                    sorted_nodes[i].name, 
                    sorted_nodes[i + 1].name
                )
                count += 1
                logger.info(f"   Created edge: {sorted_nodes[i].name} -> {sorted_nodes[i + 1].name}")
            except Exception as e:
                logger.debug(f"   Edge {sorted_nodes[i].name} -> {sorted_nodes[i + 1].name} may already exist: {e}")
        
        # last_node -> END
        try:
            self.workflow_repo.add_edge(workflow_id, sorted_nodes[-1].name, 'END')
            count += 1
            logger.info(f"   Created edge: {sorted_nodes[-1].name} -> END")
        except Exception as e:
            logger.debug(f"   Edge {sorted_nodes[-1].name} -> END may already exist: {e}")
        
        logger.info(f"   ✅ Created {count} initial edges")
        return count
    
    def _create_linear_edges_except_conditional(
        self, 
        workflow_id: int, 
        conditional_node_names: list
    ) -> int:
        """
        为非条件节点创建线性边
        条件节点的边由 _create_conditional_edges 单独处理
        
        Args:
            workflow_id: Workflow ID
            conditional_node_names: 条件节点名称列表（跳过这些节点）
            
        Returns:
            创建的边数量
        """
        workflow = self.workflow_repo.get_workflow(workflow_id)
        count = 0
        
        # 获取所有非条件节点，按 execution_order 排序
        sorted_nodes = sorted(
            [n for n in workflow.nodes if n.name not in conditional_node_names],
            key=lambda n: n.execution_order
        )
        
        if len(sorted_nodes) == 0:
            logger.warning("   No non-conditional nodes to connect")
            return 0
        
        logger.info(f"   Creating linear edges for {len(sorted_nodes)} non-conditional nodes...")
        
        # START -> first_node
        try:
            self.workflow_repo.add_edge(workflow_id, 'START', sorted_nodes[0].name)
            count += 1
            logger.info(f"   Created edge: START -> {sorted_nodes[0].name}")
        except Exception as e:
            logger.debug(f"   Edge START -> {sorted_nodes[0].name} may already exist: {e}")
        
        # node[i] -> node[i+1]
        for i in range(len(sorted_nodes) - 1):
            try:
                self.workflow_repo.add_edge(
                    workflow_id, 
                    sorted_nodes[i].name, 
                    sorted_nodes[i + 1].name
                )
                count += 1
                logger.info(f"   Created edge: {sorted_nodes[i].name} -> {sorted_nodes[i + 1].name}")
            except Exception as e:
                logger.debug(f"   Edge may already exist: {e}")
        
        # last_node -> END
        try:
            self.workflow_repo.add_edge(workflow_id, sorted_nodes[-1].name, 'END')
            count += 1
            logger.info(f"   Created edge: {sorted_nodes[-1].name} -> END")
        except Exception as e:
            logger.debug(f"   Edge may already exist: {e}")
        
        logger.info(f"   ✅ Created {count} linear edges")
        return count


# 全局便捷函数
def auto_sync_plugins(session: Session, workflow_id: int) -> Dict[str, int]:
    """
    便捷函数：自动同步插件
    
    使用示例：
        from langtrader_core.plugins.auto_sync import auto_sync_plugins
        stats = auto_sync_plugins(session, workflow_id=1)
    """
    syncer = PluginAutoSync(session)
    return syncer.sync_if_needed(workflow_id)