# packages/langtrader_core/plugins/workflow.py
"""
Workflow builder for the trading system.
"""
from tracemalloc import is_tracing
from typing import Dict, Any, Optional, List
from sqlmodel import Session, select
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from dotenv import load_dotenv
import langsmith as ls
import os

# 尽早加载环境变量，确保 LangSmith 能读取到配置
load_dotenv()

from langtrader_core.graph.state import State
from langtrader_core.data.models.bot import Bot
from langtrader_core.data.models.workflow import Workflow, WorkflowNode, WorkflowEdge
from langtrader_core.data.repositories.bot import BotRepository
from langtrader_core.data.repositories.workflow import WorkflowRepository
from langtrader_core.data.repositories.exchange import ExchangeRepository
from langtrader_core.plugins.registry import registry, PluginContext
from langtrader_core.services.llm_factory import LLMFactory
from langtrader_core.plugins.auto_sync import PluginAutoSync
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langtrader_core.utils import get_logger

logger = get_logger("workflow_builder")


class WorkflowBuilder:
    """
    Workflow builder for the trading system.
    """
    
    def __init__(self, session: Session, bot_id: int = None):
        """
         initialize the workflow builder
        """
        self.session = session
        self.bot_id = bot_id
        
        self.bot_repo = BotRepository(session)
        self.workflow_repo = WorkflowRepository(session)
        self.exchange_repo = ExchangeRepository(session)
        
        self.bot: Optional[Bot] = None
        self.workflow: Optional[Workflow] = None
        self.exchange_config: Optional[Dict] = None
        
        self.graph = None
        self.node_instances: Dict[str, Any] = {}
        self.context: Optional[PluginContext] = None
        self.llm_factory: Optional[LLMFactory] = None
        self.checkpointer_context = None # checkpoint context

    async def _create_checkpoint(self):
        """
        Create the checkpoint for the workflow
        Returns
        -------
        """
        postgresql_url = os.getenv("DATABASE_URL")
        # if sys config postgresql
        if postgresql_url:
            logger.info(f"🗄️  Creating PostgreSQL checkpointer: {postgresql_url.split('@')[-1]}")
            # create and into context
            self.checkpointer_context = AsyncPostgresSaver.from_conn_string(postgresql_url)
            checkpointer = await self.checkpointer_context.__aenter__()
            logger.info(f"checkpointer now is {checkpointer}")
        else:
            logger.warning("Sys did not provide PostgreSQL checkpointer, using InMemorySaver")
            checkpointer = InMemorySaver()

        return checkpointer

    async def cleanup(self):
        """clean sql connetions"""
        if self.checkpointer_context is not None:
            try:
                await self.checkpointer_context.__aexit__(None, None, None)
                logger.info("Checkpointer cleared!")
            except Exception as e:
                logger.error("Trying to clean up checkpointer failed!")
    
    def load_bot_config(self) -> Dict[str, Any]:
        """
        load the bot config from database
        """
        logger.info(f"📦 Loading bot configuration: bot_id={self.bot_id}")
        # auto sync plugins
        try:
            logger.debug("🔄 Auto-syncing plugins...")
            syncer = PluginAutoSync(self.session)
            
            # discover plugins
            registry.discover_plugins("langtrader_core.graph.nodes")
            
            # get target workflow id
            # if bot_id is provided, get the workflow_id; otherwise use default workflow (id=1)
            target_workflow_id = None
            
            if self.bot_id:
                bot = self.bot_repo.get_by_id(self.bot_id)
                if bot:
                    target_workflow_id = bot.workflow_id
            
            if not target_workflow_id:
                # use default workflow (id=1)
                target_workflow_id = 1
            
            # execute auto sync
            stats = syncer.sync_if_needed(target_workflow_id)
            
            if stats["added"] > 0:
                logger.info(f"✅ Auto-registered {stats['added']} new plugins")
            
        except Exception as e:
            logger.warning(f"⚠️  Plugin auto-sync failed (non-critical): {e}")

        # 1. load bot
        if self.bot_id:
            self.bot = self.bot_repo.get_by_id(self.bot_id)
        else:
            # if not specified, get the first active bot
            active_bots = self.bot_repo.get_active_bots()
            if active_bots:
                self.bot = active_bots[0]
                self.bot_id = self.bot.id
        
        if not self.bot:
            raise ValueError(f"Bot not found: bot_id={self.bot_id}")
        
        if not self.bot.is_active:
            raise ValueError(f"Bot is not active: {self.bot.name}")
        
        logger.info(f"✅ Loaded bot: {self.bot.name} (id={self.bot.id})")
        
        # 2. load exchange config
        self.exchange_config = self.exchange_repo.get_by_id(self.bot.exchange_id)
        if not self.exchange_config:
            raise ValueError(f"Exchange not found: id={self.bot.exchange_id}")
        
        logger.info(f"✅ Loaded exchange: {self.exchange_config['name']} "
                   f"({'Testnet' if self.exchange_config['testnet'] else 'Mainnet'})")
        
        # 3. load workflow
        self.workflow = self.workflow_repo.get_workflow(self.bot.workflow_id)
        if not self.workflow:
            raise ValueError(f"Workflow not found: id={self.bot.workflow_id}")
        
        logger.info(f"✅ Loaded workflow: {self.workflow.name} (id={self.workflow.id})")
        logger.info(f"   Nodes: {len(self.workflow.nodes)}")
        logger.info(f"   Edges: {len(self.workflow.edges)}")

        # 加载追踪配置（尽早设置环境变量）
        is_tracing = self.bot.enable_tracing
        tracing_key = self.bot.tracing_key
        tracing_project = self.bot.tracing_project

        
        if is_tracing:
            if tracing_key:
                # 🔑 尽早设置环境变量，确保 LangSmith 能读取到
                os.environ['LANGSMITH_API_KEY'] = tracing_key
                os.environ['LANGSMITH_TRACING'] = 'true'  # 使用字符串而非布尔值
                os.environ['LANGCHAIN_TRACING_V2'] = 'true'  # LangSmith 新版本使用这个
                os.environ['LANGCHAIN_PROJECT'] = tracing_project  # 设置项目名
                
                logger.info(f'✅ Tracing enabled: project={tracing_project}')
                logger.debug(f'   API Key: {tracing_key[:20]}...')
            else:
                logger.warning(f'⚠️  Tracing enabled but API key not found')
                logger.warning(f'   Set bot.tracing_key in database or LANGSMITH_API_KEY in .env')
                # 不抛出异常，允许继续运行但不追踪
        else:
            logger.info(f'ℹ️  Tracing disabled for bot: {self.bot.name}')
        
         # 4. load llm config
        self.llm_factory = LLMFactory(self.session)
        if self.bot.llm_id:
            llm_config = self.llm_factory.repo.get_by_id(self.bot.llm_id)
            if llm_config:
                self.llm_config = llm_config
                logger.info(f"✅ Loaded LLM config: {llm_config.name}")
            else:
                logger.warning(f"⚠️  LLM config not found: id={self.bot.llm_id}")
        else:
            llm_config = self.llm_factory.repo.get_default()
            if llm_config:
                self.llm_config = llm_config
                logger.info(f"✅ Loaded default LLM config: {llm_config.name}")
            else:
                logger.warning("⚠️  No default LLM config found")


        # 4. build full config
        full_config = {
            "bot": {
                "id": self.bot.id,
                "name": self.bot.name,
                "prompt":self.bot.prompt,
                "trading_mode": self.bot.trading_mode,
                "enable_tracing": self.bot.enable_tracing,
                "tracing_project": self.bot.tracing_project,
                "max_concurrent_symbols": self.bot.max_concurrent_symbols,
                "cycle_interval_seconds": self.bot.cycle_interval_seconds,
                "max_position_size_percent": float(self.bot.max_position_size_percent),
                "max_total_positions": self.bot.max_total_positions,
                "max_leverage": self.bot.max_leverage,
                "llm_config": self.llm_config,
                
                # 新增：量化信号配置
                "quant_signal_weights": self.bot.quant_signal_weights if hasattr(self.bot, 'quant_signal_weights') else {
                    "trend": 0.4,
                    "momentum": 0.3,
                    "volume": 0.2,
                    "sentiment": 0.1
                },
                "quant_signal_threshold": self.bot.quant_signal_threshold if hasattr(self.bot, 'quant_signal_threshold') else 50,
                
                # 新增：风险管理配置
                "risk_limits": self.bot.risk_limits if hasattr(self.bot, 'risk_limits') else {
                    "max_total_exposure_pct": 0.8,
                    "max_consecutive_losses": 5,
                    "max_single_symbol_pct": 0.3
                },
            },
            "exchange": self.exchange_config,
            "workflow": {
                "id": self.workflow.id,
                "name": self.workflow.name,
                "version": self.workflow.version,
                "category": self.workflow.category,
            }
        }

       
        
        return full_config
    
    async def build(self, context: PluginContext) -> StateGraph:
        """
        build the workflow execution graph
        
        Args:
            context: plugin context (contains trader, stream_manager, etc.)
            
        Returns:
            compiled StateGraph
        """
        logger.info("🏗️  Building workflow from database...")
        
        self.context = context
        
        # 1. load config
        config = self.load_bot_config()
        # add llm factory to context
        if self.llm_factory:
            context.llm_factory = self.llm_factory
        # 2. initialize StateGraph
        self.graph = StateGraph(State)
        
        # 3. load and instantiate nodes
        self._load_nodes()
        
        # 4. add nodes to graph
        self._add_nodes_to_graph()
        
        # 5. add edges to graph
        self._add_edges_to_graph()
        # checkpointer
        checkpointer =  await self._create_checkpoint()
        if checkpointer is None:
            logger.error(f'🚨🚨 Checkpoint not created!')
            raise  ValueError(f'🚨🚨 Checkpoint not created!')
        # 6. 编译图
        compiled_graph = self.graph.compile(checkpointer=checkpointer)
        
        logger.info("✅ Workflow built successfully from database")
        logger.info(f"   Bot: {self.bot.name}")
        logger.info(f"   Workflow: {self.workflow.name}")
        logger.info(f"   Nodes: {len(self.node_instances)}")
        logger.info(f" Checkpointer: {checkpointer}")
        
        # 保存编译后的图供后续使用
        self.compiled_graph = compiled_graph
        
        return self.compiled_graph

    
    async def run_with_tracing(self, state: State, config: Any) -> Any:
        """
        带追踪的运行方法
        根据 Bot 配置决定是否启用 LangSmith 追踪
        
        Args:
            state: 当前状态
            config: 运行配置
            
        Returns:
            执行结果
        """
        if not hasattr(self, 'compiled_graph'):
            raise ValueError("Graph not built yet. Call build() first.")
        
        # 检查追踪配置
        api_key = os.environ.get('LANGSMITH_API_KEY')
        tracing_enabled = os.environ.get('LANGCHAIN_TRACING_V2', 'false')
        
        if self.bot.enable_tracing and api_key:
            logger.info(f"🔍 Running with LangSmith tracing: {self.bot.tracing_project}")
            logger.debug(f"   LANGCHAIN_TRACING_V2={tracing_enabled}")
            logger.debug(f"   LANGCHAIN_PROJECT={os.environ.get('LANGCHAIN_PROJECT')}")
            
            # 使用追踪上下文（参数与旧版本保持一致）
            with ls.tracing_context(
                project_name=self.bot.tracing_project, 
                enabled=tracing_enabled  # 使用字符串环境变量
            ):
                return await self.compiled_graph.ainvoke(state, config)
        else:
            # 不追踪，直接运行
            if self.bot.enable_tracing:
                logger.warning("⚠️  Tracing disabled: no API key found")
            return await self.compiled_graph.ainvoke(state, config)
    
    def _load_nodes(self):
        """load nodes from database and create instances"""
        if not self.workflow or not self.workflow.nodes:
            logger.warning("No nodes found in workflow")
            return
        
        # sort nodes by execution order
        sorted_nodes = sorted(self.workflow.nodes, key=lambda n: n.execution_order)
        
        for node in sorted_nodes:
            if not node.enabled:
                logger.info(f"⏭️  Skipping disabled node: {node.name}")
                continue
            
            try:
                # get node config
                config = self.workflow_repo.get_node_config_dict(node.id)
                
                logger.info(f"📦 Loading node: {node.name} (plugin: {node.plugin_name})")
                logger.debug(f"   Config: {config}")
                
                # create plugin instance
                instance = registry.create_instance(
                    name=node.plugin_name,
                    context=self.context,
                    config=config
                )
                
                if instance:
                    self.node_instances[node.name] = instance
                    logger.info(f"✅ Node loaded: {node.name}")
                else:
                    logger.error(f"❌ Failed to create instance for: {node.name}")
                    
            except Exception as e:
                logger.error(f"❌ Failed to load node '{node.name}': {e}")
                raise
    
    def _add_nodes_to_graph(self):
        """add nodes to LangGraph"""
        logger.debug("Adding nodes to graph...")
        
        for node_name, instance in self.node_instances.items():
            self.graph.add_node(node_name, instance.run)
            logger.debug(f"  ✓ Added node: {node_name}")
    
    def _add_edges_to_graph(self):
        """add edges to LangGraph from database（支持条件边）"""
        if not self.workflow or not self.workflow.edges:
            logger.warning("No edges found in workflow, using default linear flow")
            self._add_default_edges()
            return
        
        logger.debug("Adding edges to graph...")
        
        # 🎯 分组边：普通边 vs 条件边
        normal_edges = []
        conditional_edges_map = {}  # {from_node: [(condition, to_node), ...]}
        
        for edge in self.workflow.edges:
            # handle special nodes START and END
            from_node = START if edge.from_node == "START" else edge.from_node
            to_node = END if edge.to_node == "END" else edge.to_node
            
            # validate nodes exist
            if edge.from_node not in ["START"] and edge.from_node not in self.node_instances:
                logger.warning(f"⚠️  From node not found: {edge.from_node}, skipping edge")
                continue
            
            if edge.to_node not in ["END"] and edge.to_node not in self.node_instances:
                logger.warning(f"⚠️  To node not found: {edge.to_node}, skipping edge")
                continue
            
            # 🎯 区分普通边和条件边
            if edge.condition:
                # 条件边
                if from_node not in conditional_edges_map:
                    conditional_edges_map[from_node] = []
                conditional_edges_map[from_node].append((edge.condition, to_node))
                logger.debug(f"  Found conditional edge: {from_node} -[{edge.condition}]-> {to_node}")
            else:
                # 普通边
                normal_edges.append((from_node, to_node))
        
        # 添加普通边
        for from_node, to_node in normal_edges:
            self.graph.add_edge(from_node, to_node)
            logger.debug(f"  ✓ Added edge: {from_node} -> {to_node}")
        
        # 🎯 添加条件边
        for from_node, conditions in conditional_edges_map.items():
            # 构建路由映射
            route_map = {cond: target for cond, target in conditions}
            
            # 🎯 创建条件判断函数
            def make_condition_func(node_name):
                """工厂函数：为每个节点创建独立的条件函数"""
                def condition_router(state):
                    # 从 state 中获取条件值
                    # 优先级：1) state.{node_name}_result  2) state.condition_result
                    condition_key = f"{node_name}_result"
                    result = getattr(state, condition_key, None)
                    if result is None:
                        result = getattr(state, "condition_result", "default")
                    logger.debug(f"Condition router for '{node_name}': {result}")
                    return result
                return condition_router
            
            condition_func = make_condition_func(from_node)
            
            self.graph.add_conditional_edges(
                from_node,
                condition_func,
                route_map
            )
            logger.info(f"  ✓ Added conditional edges: {from_node} -> {list(route_map.keys())}")
    
    def _add_default_edges(self):
        """add default linear edges (when no edges defined in database)"""
        node_names = list(self.node_instances.keys())
        
        if not node_names:
            logger.warning("No nodes to connect")
            return
        
        # START -> first node
        self.graph.add_edge(START, node_names[0])
        
        # connect nodes
        for i in range(len(node_names) - 1):
            self.graph.add_edge(node_names[i], node_names[i + 1])
        
        # last node -> END
        self.graph.add_edge(node_names[-1], END)
        
        logger.info(f"✅ Added default linear edges for {len(node_names)} nodes")
    
    def list_available_workflows(self) -> List[str]:
        """list all available workflows"""
        statement = select(Workflow)
        workflows = self.session.exec(statement).all()
        return [w.name for w in workflows]
    
    def get_bot_config_summary(self) -> Dict[str, Any]:
        """get bot config summary (for logging or UI display)"""
        if not self.bot:
            return {}
        
        return {
            "bot_id": self.bot.id,
            "bot_name": self.bot.name,
            "exchange": self.exchange_config.get('name') if self.exchange_config else None,
            "testnet": self.exchange_config.get('testnet') if self.exchange_config else None,
            "workflow": self.workflow.name if self.workflow else None,
            "trading_mode": self.bot.trading_mode,
            "is_active": self.bot.is_active,
            "max_concurrent_symbols": self.bot.max_concurrent_symbols,
            "tracing_enabled": self.bot.enable_tracing,
        }


class WorkflowManager:
    """
    Workflow manager
    provide advanced API for managing multiple workflows
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.workflow_repo = WorkflowRepository(session)
        self.bot_repo = BotRepository(session)
    
    def list_workflows(self) -> List[Workflow]:
        """list all workflows"""
        statement = select(Workflow)
        return self.session.exec(statement).all()
    
    def list_bots(self) -> List[Bot]:
        """list all bots"""
        statement = select(Bot)
        return self.session.exec(statement).all()
    
    def get_active_bots(self) -> List[Bot]:
        """get all active bots"""
        return self.bot_repo.get_active_bots()
    
    def build_bot_workflow(
        self, 
        bot_id: int, 
        context: PluginContext
    ) -> StateGraph:
        """
        build workflow for specified bot
        
        Args:
            bot_id: Bot ID
            context: plugin context
            
        Returns:
            compiled StateGraph
        """
        builder = WorkflowBuilder(self.session, bot_id)
        return builder.build(context)
    
    def get_bot_full_config(self, bot_id: int) -> Dict[str, Any]:
        """
        get bot full config (including Exchange and Workflow)
        
        Args:
            bot_id: Bot ID
            
        Returns:
            full config dictionary
        """
        builder = WorkflowBuilder(self.session, bot_id)
        return builder.load_bot_config()