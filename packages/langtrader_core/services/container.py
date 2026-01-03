# packages/langtrader_core/services/container.py
"""
服务容器 - 统一管理共享服务实例
实现依赖注入模式，避免服务重复创建
"""
from sqlmodel import Session

from langtrader_core.services.singleton import Singleton
from langtrader_core.services.cache import Cache
from langtrader_core.services.ratelimit import RateLimiter
from langtrader_core.services.config_manager import SystemConfig
from langtrader_core.utils import get_logger

logger = get_logger("container")


class ServiceContainer(Singleton):
    """
    服务容器（单例）
    继承 Singleton 基类实现线程安全的单例
    管理所有共享服务实例：Cache, RateLimiter, SystemConfig
    """
    
    def _init_singleton(self):
        """初始化服务容器"""
        self.cache = None
        self.rate_limiter = None
        self.system_config = SystemConfig()
        self.session = None
        self._session_lock = __import__('threading').Lock()
        logger.info("Service container initialized")
    
    def initialize(self, session: Session):
        """
        使用数据库会话初始化服务
        
        Args:
            session: 数据库会话
        """
        with self._session_lock:
            if self.session is not None:
                logger.debug("Container already initialized with session")
                return
        
        self.session = session
        
        # 加载系统配置
        logger.info("Loading system configurations...")
        self.system_config.load(session)
        
        # 初始化 Cache（使用数据库配置的TTL）
        logger.info("Initializing cache service...")
        self.cache = Cache()  # Cache 是单例，不能传参数
        
        # 手动加载数据库配置到 Cache
        try:
            cache_ttls = self.system_config.get_all_cache_ttls(session)
            if cache_ttls:
                self.cache.cache_ttl.update(cache_ttls)
                logger.info(f"Cache TTL updated from database ({len(cache_ttls)} types)")
        except Exception as e:
            logger.warning(f"Failed to update cache TTL from database: {e}")
        
        # 初始化 RateLimiter
        logger.info("Initializing rate limiter...")
        self.rate_limiter = RateLimiter()
        
        logger.info("✅ Service container fully initialized")
    
    @classmethod
    def get_instance(cls, session: Session = None):
        """
        获取容器实例
        
        Args:
            session: 数据库会话（首次调用时必须提供）
            
        Returns:
            ServiceContainer 实例
        """
        instance = cls()
        
        if session and not instance.session:
            instance.initialize(session)
        
        return instance
    
    def get_cache(self) -> Cache:
        """获取 Cache 服务"""
        if self.cache is None:
            raise RuntimeError("Container not initialized. Call initialize(session) first.")
        return self.cache
    
    def get_rate_limiter(self) -> RateLimiter:
        """获取 RateLimiter 服务"""
        if self.rate_limiter is None:
            raise RuntimeError("Container not initialized. Call initialize(session) first.")
        return self.rate_limiter
    
    def get_system_config(self) -> SystemConfig:
        """获取 SystemConfig 服务"""
        return self.system_config
    
    def reload_config(self):
        """重新加载配置（热更新）"""
        if self.session:
            logger.info("Reloading system configurations...")
            self.system_config.reload(self.session)
            
            # 只更新 Cache TTL，不重新创建（Cache 是单例）
            try:
                cache_ttls = self.system_config.get_all_cache_ttls(self.session)
                if cache_ttls and self.cache:
                    self.cache.cache_ttl.update(cache_ttls)
                    logger.info(f"Cache TTL reloaded ({len(cache_ttls)} types)")
            except Exception as e:
                logger.warning(f"Failed to reload cache TTL: {e}")
            
            logger.info("Configuration reloaded")
        else:
            logger.warning("Cannot reload config: no session available")

