# packages/langtrader_core/plugins/protocol.py
"""
插件协议定义
定义了所有节点插件必须遵循的接口和元数据结构
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict
from langtrader_core.graph.state import State
from langtrader_core.utils import get_logger

if TYPE_CHECKING:
    from langtrader_core.plugins.registry import PluginContext

logger = get_logger("plugin_protocol")


class NodeMetadata(BaseModel):
    """
    节点元数据
    描述插件的基本信息、依赖关系和配置要求
    """
    model_config = ConfigDict(extra="allow")
    
    # 基本信息
    name: str = Field(..., description="节点唯一标识符，如 'coins_pick'")
    display_name: str = Field(..., description="显示名称，如 'Coin Selection'")
    version: str = Field(..., description="版本号，如 '1.0.0'")
    author: str = Field(..., description="作者")
    description: str = Field(default="", description="节点描述")
    
    # 分类
    category: str = Field(
        default="general",
        description="类别：data_source, analysis, decision, execution, monitoring"
    )
    tags: List[str] = Field(default_factory=list, description="标签")
    
    # 输入输出声明
    inputs: List[str] = Field(
        default_factory=list,
        description="输入依赖的 State 字段，如 ['symbols', 'market_data']"
    )
    outputs: List[str] = Field(
        default_factory=list,
        description="输出的 State 字段，如 ['market_data', 'indicators']"
    )
    
    # 依赖关系
    requires: List[str] = Field(
        default_factory=list,
        description="必需的前置节点，如 ['coins_pick']"
    )
    optional_requires: List[str] = Field(
        default_factory=list,
        description="可选的前置节点"
    )
    
    # 资源需求
    requires_trader: bool = Field(default=False, description="是否需要交易所连接")
    requires_llm: bool = Field(default=False, description="是否需要 LLM")
    requires_database: bool = Field(default=False, description="是否需要数据库")
    
    # 配置
    config_schema: Optional[Dict[str, Any]] = Field(
        default=None,
        description="JSON Schema 定义配置结构"
    )
    default_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="默认配置"
    )

     # 🎯 新增：自动连接配置
    insert_after: Optional[str] = Field(
        default=None,
        description="建议插入到哪个节点之后（用于自动连接工作流）"
    )
    insert_before: Optional[str] = Field(
        default=None,
        description="建议插入到哪个节点之前（用于自动连接工作流）"
    )
    suggested_order: Optional[int] = Field(
        default=None,
        description="建议的执行顺序（数字越小越先执行）"
    )
    
    # 🎯 新增：自动注册控制
    auto_register: bool = Field(
        default=True,
        description="是否允许自动注册到数据库"
    )

    # add condition edge
    is_conditional: bool = Field(
        default=False,
        description="是否为条件节点（有多个可能的下游分支）"
    )
    
    conditional_routes: Optional[Dict[str, str]] = Field(
        default=None,
        description="条件路由映射：{条件值: 目标节点名}，例如 {'approved': 'execution', 'rejected': 'END'}"
    )
    
    condition_function: Optional[str] = Field(
        default=None,
        description="条件判断函数名，用于从 state 中提取条件值"
    )
    
    # 兼容性
    min_core_version: str = Field(
        default="0.1.0",
        description="最低核心版本要求"
    )


class NodePlugin(ABC):
    """
    节点插件基类
    所有节点必须继承此类并实现 run 方法
    """
    
    # 子类必须定义 metadata
    metadata: NodeMetadata
    
    def __init__(
        self, 
        context: Optional['PluginContext'] = None,
        config: Optional[Dict] = None
    ):
        """
        初始化节点
        
        Args:
            context: 插件上下文（提供共享资源）
            config: 节点配置（从配置文件加载）
        """
        self.context = context
        self._raw_config = config or {}
        self.config = {**self.metadata.default_config, **self._raw_config}
        self._validate_config()
    
    # ==================== 公共配置加载方法 ====================
    
    def load_config_from_database(self, prefix: str = None) -> Dict[str, Any]:
        """
        从数据库加载节点配置
        
        Args:
            prefix: 配置前缀，如 'batch_decision'、'debate'
                   如果不提供，使用 metadata.name
            
        Returns:
            配置字典
        """
        prefix = prefix or self.metadata.name
        
        if not self.context or not hasattr(self.context, 'database'):
            return {}
        
        database = getattr(self.context, 'database', None)
        if not database:
            return {}
        
        config = {}
        try:
            from langtrader_core.services.config_manager import SystemConfig
            
            # database 可能是 Session 对象或有 get_session 方法的 wrapper
            if hasattr(database, 'get_session'):
                with database.get_session() as session:
                    system_config = SystemConfig(session)
                    all_configs = system_config.get_by_prefix(prefix)
            else:
                # database 直接是 Session 对象
                system_config = SystemConfig(database)
                all_configs = system_config.get_by_prefix(prefix)
            
            for key, value in all_configs.items():
                # 移除前缀，如 'batch_decision.timeout' -> 'timeout'
                short_key = key.replace(f"{prefix}.", "")
                config[short_key] = value
                    
        except Exception as e:
            logger.warning(f"⚠️ Failed to load config from database ({prefix}): {e}")
        
        return config
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值
        
        优先级：实例配置 > 数据库配置 > 默认值
        """
        return self.config.get(key, default)
    
    def merge_config(self, db_config: Dict[str, Any], default_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并配置（便捷方法）
        
        优先级：实例配置 > 数据库配置 > 默认配置
        """
        return {**default_config, **db_config, **self._raw_config}
    
    @abstractmethod
    async def run(self, state: State) -> State:
        """
        执行节点逻辑（必须实现）
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        pass
    
    async def setup(self):
        """
        节点启动时的初始化（可选重写）
        在 workflow 构建后、执行前调用
        """
        pass
    
    async def teardown(self):
        """
        节点关闭时的清理（可选重写）
        在 workflow 执行完成后调用
        """
        pass
    
    def validate(self) -> bool:
        """
        验证节点配置和依赖（可选重写）
        
        Returns:
            是否验证通过
        """
        return True
    
    def _validate_config(self):
        """
        验证配置是否符合 config_schema
        使用 jsonschema 进行验证
        """
        if not self.metadata.config_schema:
            return
        
        try:
            from jsonschema import validate, ValidationError
            
            validate(
                instance=self.config,
                schema=self.metadata.config_schema
            )
            
            logger.debug(f"✅ Config validation passed: {self.metadata.name}")
            
        except ImportError:
            logger.warning(
                "jsonschema not installed, skipping config validation. "
                "Install with: pip install jsonschema"
            )
        except Exception as e:
            error_msg = (
                f"❌ Invalid config for '{self.metadata.name}': {str(e)}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg) from e
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        健康检查（可选重写）
        
        Returns:
            健康状态信息
        """
        return {
            "status": "healthy",
            "node": self.metadata.name,
            "version": self.metadata.version
        }
    
    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"name={self.metadata.name} "
            f"version={self.metadata.version}>"
        )


class ConditionalNode(NodePlugin):
    """
    条件节点基类
    支持根据 state 判断是否执行
    """
    
    @abstractmethod
    def should_execute(self, state: State) -> bool:
        """
        判断是否应该执行（必须实现）
        
        Args:
            state: 当前状态
            
        Returns:
            是否执行
        """
        pass
    
    async def run(self, state: State) -> State:
        """
        根据条件决定是否执行
        """
        if self.should_execute(state):
            logger.info(f"✅ Condition met, executing: {self.metadata.name}")
            return await self.execute(state)
        else:
            logger.info(f"⏭️  Condition not met, skipping: {self.metadata.name}")
            return state
    
    @abstractmethod
    async def execute(self, state: State) -> State:
        """
        实际执行逻辑（必须实现）
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态
        """
        pass


# 导出
__all__ = [
    'NodeMetadata',
    'NodePlugin',
    'ConditionalNode',
]