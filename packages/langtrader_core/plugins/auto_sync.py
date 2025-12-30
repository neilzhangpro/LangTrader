# packages/langtrader_core/plugins/auto_sync.py
"""
插件自动同步模块
在系统启动时自动将插件同步到数据库，支持边自动创建和条件边
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
    插件自动同步器
    在系统启动时自动将新插件注册到数据库
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
        增量同步插件到数据库（幂等操作，线程安全）
        
        Args:
            workflow_id: 目标 workflow ID
            
        Returns:
            统计信息 {"existing": 4, "added": 1, "failed": 0}
        """
        # 🔒 获取 workflow 级别的锁
        lock = self._get_lock(workflow_id)
        
        with lock:
            logger.debug(f"🔒 Acquired sync lock for workflow {workflow_id}")
            
            stats = {"existing": 0, "added": 0, "failed": 0, "edges_created": 0}
            
            try:
                # 获取工作流
                workflow = self.workflow_repo.get_workflow(workflow_id)
                if not workflow:
                    logger.warning(f"⚠️  Workflow {workflow_id} not found, skipping auto-sync")
                    return stats
                
                # 获取已注册的插件
                discovered_plugins = registry._metadata  # {name: NodeMetadata}
                existing_nodes = {node.plugin_name: node for node in workflow.nodes}
                
                # 找出新插件
                new_plugins = []
                for plugin_name, metadata in discovered_plugins.items():
                    if not metadata.auto_register:
                        continue
                    
                    if plugin_name in existing_nodes:
                        stats["existing"] += 1
                    else:
                        new_plugins.append((plugin_name, metadata))
                
                # 如果没有新插件
                if not new_plugins:
                    logger.debug(f"✓ All {stats['existing']} plugins already registered")
                    # 🎯 即使没有新插件，也检查边是否需要创建
                    workflow = self.workflow_repo.get_workflow(workflow_id)
                    if not workflow.edges and len(workflow.nodes) > 0:
                        logger.info(f"🔗 No edges found, creating initial edges...")
                        initial_edges = self._create_initial_edges(workflow_id)
                        stats["edges_created"] += initial_edges
                    return stats
                
                # 🎯 改进：分两个阶段
                # 阶段1：先创建所有节点（不创建边）
                logger.info(f"🔄 Phase 1: Creating {len(new_plugins)} nodes...")
                
                for plugin_name, metadata in new_plugins:
                    try:
                        self._create_node_only(workflow_id, metadata)
                        stats["added"] += 1
                        logger.info(f"✅ Created node: {plugin_name} (order={metadata.suggested_order})")
                    except Exception as e:
                        stats["failed"] += 1
                        logger.error(f"❌ Failed to create node '{plugin_name}': {e}")
                
                # 阶段2：统一创建所有边
                if stats["added"] > 0:
                    logger.info(f"🔄 Phase 2: Creating edges for all nodes...")
                    workflow = self.workflow_repo.get_workflow(workflow_id)  # 重新加载
                    
                    if not workflow.edges:
                        # 如果没有边，创建完整的初始边
                        logger.info(f"   No existing edges, creating complete edge set...")
                        edges_count = self._create_initial_edges(workflow_id)
                        stats["edges_created"] += edges_count
                    else:
                        # 如果有边，为新节点插入边
                        logger.info(f"   Existing edges found, inserting new nodes...")
                        for plugin_name, metadata in new_plugins:
                            try:
                                edges_count = self._connect_node(workflow_id, plugin_name, metadata)
                                stats["edges_created"] += edges_count
                            except Exception as e:
                                logger.error(f"❌ Failed to connect '{plugin_name}': {e}")
                
                if stats["added"] > 0:
                    logger.info(f"✅ Auto-sync completed: {stats['added']} plugins, {stats['edges_created']} edges")
                
            except Exception as e:
                logger.error(f"❌ Auto-sync failed: {e}")
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
    
    def _connect_node(self, workflow_id: int, plugin_name: str, metadata: NodeMetadata) -> int:
        """为单个节点创建边连接"""
        workflow = self.workflow_repo.get_workflow(workflow_id)
        
        if metadata.is_conditional and metadata.conditional_routes:
            # 条件节点
            return self._create_conditional_edges(workflow_id, plugin_name, metadata)
        elif metadata.insert_after:
            # 普通节点
            return self._insert_after(workflow, plugin_name, metadata.insert_after)
        elif metadata.insert_before:
            return self._insert_before(workflow, plugin_name, metadata.insert_before)
        
        return 0
    
    
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
        
        # 🎯 还需要创建到达此条件节点的边
        if metadata.insert_after:
            upstream_count = self._connect_upstream(workflow_id, node_name, metadata.insert_after)
            count += upstream_count
        
        return count
    
    def _insert_after(self, workflow, node_name: str, after_node: str) -> int:
        """
        将节点插入到指定节点之后
        
        Returns:
            创建的边数量
        """
        count = 0
        
        logger.info(f"   Attempting to insert '{node_name}' after '{after_node}'")
        
        # 🎯 改进：优先从现有边查找，失败则从 execution_order 推断
        downstream = self._find_downstream(workflow, after_node)
        
        logger.info(f"   Found downstream: {downstream}")
        
        if not downstream:
            logger.warning(f"   Cannot determine downstream of '{after_node}', edge creation skipped")
            return 0
        
        # 删除旧边（如果存在）
        for edge in workflow.edges:
            if edge.from_node == after_node and edge.to_node == downstream:
                self.session.delete(edge)
                self.session.commit()
                logger.debug(f"   Removed old edge: {after_node} -> {downstream}")
                break
        
        # 添加新边
        try:
            self.workflow_repo.add_edge(workflow.id, after_node, node_name)
            count += 1
            self.workflow_repo.add_edge(workflow.id, node_name, downstream)
            count += 1
            logger.info(f"   ✅ Connected: {after_node} -> {node_name} -> {downstream}")
        except Exception as e:
            logger.error(f"   ❌ Failed to create edges: {e}")
        
        return count
    
    def _insert_before(self, workflow, node_name: str, before_node: str) -> int:
        """
        将节点插入到指定节点之前
        
        Returns:
            创建的边数量
        """
        count = 0
        
        logger.info(f"   Attempting to insert '{node_name}' before '{before_node}'")
        
        # 🎯 改进：优先从现有边查找，失败则从 execution_order 推断
        upstream = self._find_upstream(workflow, before_node)
        
        logger.info(f"   Found upstream: {upstream}")
        
        if not upstream:
            logger.warning(f"   Cannot determine upstream of '{before_node}', edge creation skipped")
            return 0
        
        # 删除旧边（如果存在）
        for edge in workflow.edges:
            if edge.from_node == upstream and edge.to_node == before_node:
                self.session.delete(edge)
                self.session.commit()
                logger.debug(f"   Removed old edge: {upstream} -> {before_node}")
                break
        
        # 添加新边
        try:
            self.workflow_repo.add_edge(workflow.id, upstream, node_name)
            count += 1
            self.workflow_repo.add_edge(workflow.id, node_name, before_node)
            count += 1
            logger.info(f"   ✅ Connected: {upstream} -> {node_name} -> {before_node}")
        except Exception as e:
            logger.error(f"   ❌ Failed to create edges: {e}")
        
        return count
    
    def _connect_upstream(self, workflow_id: int, node_name: str, upstream_node: str) -> int:
        """
        仅创建上游到当前节点的边（用于条件节点）
        
        Returns:
            创建的边数量
        """
        try:
            self.workflow_repo.add_edge(workflow_id, upstream_node, node_name)
            logger.debug(f"   ✅ Upstream edge: {upstream_node} -> {node_name}")
            return 1
        except Exception as e:
            logger.error(f"   ❌ Failed to create upstream edge: {e}")
            return 0
    
    def _find_downstream(self, workflow, node_name: str) -> str:
        """
        智能查找下游节点
        1. 优先从现有边查找
        2. 失败则从 execution_order 推断
        """
        logger.debug(f"   _find_downstream: looking for downstream of '{node_name}'")
        
        # 方法1：从现有边查找
        for edge in workflow.edges:
            if edge.from_node == node_name:
                logger.debug(f"   Found from edges: {edge.to_node}")
                return edge.to_node
        
        # 方法2：从 execution_order 推断
        current_order = None
        for node in workflow.nodes:
            if node.name == node_name:
                current_order = node.execution_order
                break
        
        logger.debug(f"   Node '{node_name}' has order={current_order}")
        
        if current_order is None:
            logger.warning(f"   Node '{node_name}' not found in workflow!")
            return None
        
        # 找到执行顺序最接近的下一个节点
        next_nodes = [n for n in workflow.nodes if n.execution_order > current_order]
        
        logger.debug(f"   Found {len(next_nodes)} nodes with order > {current_order}")
        for n in next_nodes[:3]:
            logger.debug(f"     - {n.name} (order={n.execution_order})")
        
        if not next_nodes:
            logger.debug(f"   No downstream nodes, returning END")
            return "END"
        
        next_nodes.sort(key=lambda n: n.execution_order)
        downstream = next_nodes[0].name
        
        logger.debug(f"   Returning downstream: {downstream}")
        
        return downstream
    
    def _find_upstream(self, workflow, node_name: str) -> str:
        """
        智能查找上游节点
        1. 优先从现有边查找
        2. 失败则从 execution_order 推断
        """
        logger.debug(f"   _find_upstream: looking for upstream of '{node_name}'")
        
        # 方法1：从现有边查找
        for edge in workflow.edges:
            if edge.to_node == node_name:
                logger.debug(f"   Found from edges: {edge.from_node}")
                return edge.from_node
        
        # 方法2：从 execution_order 推断
        current_order = None
        for node in workflow.nodes:
            if node.name == node_name:
                current_order = node.execution_order
                break
        
        logger.debug(f"   Node '{node_name}' has order={current_order}")
        
        if current_order is None:
            logger.warning(f"   Node '{node_name}' not found in workflow!")
            return None
        
        # 找到执行顺序最接近的上一个节点
        prev_nodes = [n for n in workflow.nodes if n.execution_order < current_order]
        
        logger.debug(f"   Found {len(prev_nodes)} nodes with order < {current_order}")
        
        if not prev_nodes:
            logger.debug(f"   No upstream nodes, returning START")
            return "START"
        
        prev_nodes.sort(key=lambda n: n.execution_order, reverse=True)
        upstream = prev_nodes[0].name
        
        logger.debug(f"   Returning upstream: {upstream}")
        
        return upstream
    
    def _create_initial_edges(self, workflow_id: int) -> int:
        """
        为所有节点创建初始边（当 workflow.edges 为空时）
        基于 execution_order 创建线性流程
        
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