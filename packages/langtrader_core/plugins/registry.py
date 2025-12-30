from typing import Dict, List, Type, Optional, Any, TYPE_CHECKING
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.utils import get_logger
from dataclasses import dataclass, field
import importlib
import pkgutil
import inspect

logger = get_logger("plugin_registry")

# 类型提示（避免循环导入）
if TYPE_CHECKING:
    from langtrader_core.services.trader import Trader
    from langtrader_core.services.stream_manager import DynamicStreamManager
    from langtrader_core.services.cache import Cache
    from langtrader_core.services.ratelimit import RateLimiter
    from langtrader_core.services.llm_factory import LLMFactory
    from langtrader_core.services.performance import PerformanceService
    from langtrader_core.data.repositories.trade_history import TradeHistoryRepository


@dataclass
class PluginContext:
    """
    插件上下文：提供共享资源（依赖注入容器）
    所有服务从这里获取共享实例，避免重复创建
    """
    trader: Optional['Trader'] = None
    stream_manager: Optional['DynamicStreamManager'] = None
    database: Optional[Any] = None
    cache: Optional['Cache'] = None
    rate_limiter: Optional['RateLimiter'] = None
    llm_factory: Optional['LLMFactory'] = None
    trade_history_repo: Optional['TradeHistoryRepository'] = None
    performance_service: Optional['PerformanceService'] = None
    config: Dict[str, Any] = field(default_factory=dict)

class PluginRegistry:
    """
    Plugin registry: manage and register plugins
    """
    def __init__(self):
        self._plugins: Dict[str, Type[NodePlugin]] = {}
        self._instances: Dict[str, NodePlugin] = {}
        self._metadata: Dict[str, NodeMetadata] = {}
        self._discovered_packages = set() # set of discovered packages
        logger.info("Plugin Registry initialized")

    def register(self,plugin_class: Type[NodePlugin]):
        # register by manually
        # check if plugin_class is a subclass of NodePlugin
        if not hasattr(plugin_class, 'metadata'):
            logger.error(f"🙅 Plugin {plugin_class.__name__} must have 'metadata' attribute")
            raise ValueError(f"Plugin {plugin_class.__name__} must have 'metadata' attribute")
        
        # get metadata
        metadata = plugin_class.metadata
        name = metadata.name

        # must unique name
        if name in self._plugins:
            # allow to overwrite
            logger.warning(f"⚠️ Plugin {name} already registered, will overwrite")
        
        # register plugin class
        self._plugins[name] = plugin_class
        self._metadata[name] = metadata
        
        logger.info(f"✅ Registered plugin: {name} (v{metadata.version}) by {metadata.author}")
    
    def discover_plugins(self, package_name: str = "langtrader_core.graph.nodes"):
        # discover plugins in a package
        # scan all modules in the package
        
        # 🎯 幂等性检查：避免重复发现
        if package_name in self._discovered_packages:
            logger.debug(f"Package {package_name} already discovered, skipping")
            return
        
        logger.info(f"🔍 Discovering plugins in package: {package_name}")

        try:
            # import the package
            # try to using importlib to import the package
            package = importlib.import_module(package_name)
            package_path = package.__path__
            # walk through all modules in the package
            for importer, modname, ispkg in pkgutil.walk_packages(
                path=package_path, 
                prefix=f"{package_name}."
            ):
            #try to import the module
                try:
                    module = importlib.import_module(modname)
                    # find all NodePlugin subclasses in the module
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, NodePlugin) and obj != NodePlugin:
                            self.register(obj)
                            logger.info(f"✅ Discovered plugin: {name} from {modname}")
                except Exception as e:
                    logger.error(f"🚨 Failed to import module: {modname}")
                    raise ValueError(f"Failed to import module: {modname}") from e
        
            # 🎯 标记包已被发现
            self._discovered_packages.add(package_name)
        
        except Exception as e:
            logger.error(f"🚨 Failed to discover plugins in package: {package_name}")
            raise ValueError(f"Failed to discover plugins in package: {package_name}") from e

    
    def discover_from_entrypoints(self):
        """
        Discover plugins from entrypoints
        """
        logger.info("🔍 Discovering plugins from entrypoints")
        try:
            import importlib.metadata as importlib_metadata
        except ImportError:
            import importlib_metadata
        
        logger.info("🔍 Discovering plugins from entry_points...")
        entry_points = importlib_metadata.entry_points()

        #get langtrader.plugins group
        if hasattr(entry_points, 'select'):
            #python 3.10+
            plugin_eps = entry_points.select(group='langtrader.plugins')
        else:
            plugin_eps = entry_points.get('langtrader.plugins', [])
        
        #load
        for ep in plugin_eps:
            try:
                plugin_class = ep.load()
                if issubclass(plugin_class, NodePlugin) and plugin_class != NodePlugin:
                    self.register(plugin_class)
                    logger.info(f"✅ Discovered plugin: {plugin_class.__name__} from {ep.name}")
            except Exception as e:
                logger.error(f"🚨 Failed to load plugin: {ep.name}")
                raise ValueError(f"Failed to load plugin: {ep.name}") from e
        
        logger.info("🔍 Discovered plugins from entry_points")

    
    def list_plugins(self, category: Optional[str] = None) -> List[NodeMetadata]:
        # list all plugins
        # if category is provided, list only plugins in the category
        # return a list of NodeMetadata
        logger.info("🔍 Listing plugins")
        plugins = []
        for name, metadata in self._metadata.items():
            if category is None or metadata.category == category:
                plugins.append(metadata)
                logger.info(f"✅ Listed plugin: {name} (v{metadata.version}) by {metadata.author}")
        logger.info(f"✅ Listed {len(plugins)} plugins")
        return plugins
    
    def create_instance(
        self, 
        name: str, 
        context: Optional[PluginContext] = None,
        config: Optional[Dict] = None
    ) -> Optional[NodePlugin]:
        # create a plugin instance
        # args: name: str, context: PluginContext, config: Dict
        # return: NodePlugin
        logger.info(f"🔍 Creating instance of plugin: {name}")
        plugin_class = self._plugins.get(name)
        if not plugin_class:
            logger.error(f"🚨 Plugin {name} not found")
            return None
        
        try:
            # create instance
            instance = plugin_class(context=context, config=config)
            self._instances[name] = instance
            logger.info(f"✅ Created instance of plugin: {name}")
            return instance
        except Exception as e:
            logger.error(f"🚨 Failed to create instance of plugin: {name}")
            logger.error(f"   Error details: {e}", exc_info=True)
            return None
        
    def validate_dependencies(self, node_names: List[str]) -> bool:
        # validate dependencies of plugins
        # args: node_names: List[str]
        # return: bool
        logger.info(f"🔍 Validating dependencies of plugins: {node_names}")
        for name in node_names:
            metadata = self._metadata.get(name)
            if not metadata:
                logger.error(f"🚨 Plugin {name} not found")
                return False
            
            #check all dependencies nodes
            for required in metadata.requires:
                if required not in node_names:
                    logger.error(f"🚨 Plugin {name} requires plugin {required}")
                    return False
        return True
    
#register global
registry = PluginRegistry()