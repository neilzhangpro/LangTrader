# packages/langtrader_core/services/config_manager.py
"""
配置管理服务
- SystemConfig: 系统全局配置管理（从 system_configs 表加载）
- BotConfig: Bot 特定配置封装（从 bots 表读取）
"""
from typing import Any, Dict, List, Optional
from sqlmodel import Session, select, text
from langtrader_core.utils import get_logger
import time
import json

logger = get_logger("config_manager")


class SystemConfig:
    """
    系统配置管理
    从 system_configs 表加载配置，支持缓存和热更新
    
    支持两种使用方式：
    1. 类方法（全局缓存）：SystemConfig.get('key', session=session)
    2. 实例方法（带会话）：config = SystemConfig(session); config.get('key')
    """
    _cache: Dict[str, Any] = {}
    _cache_timestamp: float = 0
    _cache_ttl: int = 60  # 配置缓存60秒
    
    def __init__(self, session: Session = None):
        """
        初始化配置管理器实例
        
        Args:
            session: 数据库会话
        """
        self._session = session
        # 确保缓存已加载
        if session and not self._cache:
            self.load(session)
    
    @classmethod
    def load(cls, session: Session) -> Dict[str, Any]:
        """
        从数据库加载系统配置
        
        Args:
            session: 数据库会话
            
        Returns:
            配置字典
        """
        now = time.time()
        
        # 检查缓存
        if now - cls._cache_timestamp < cls._cache_ttl and cls._cache:
            logger.debug(f"Using cached system configs ({len(cls._cache)} items)")
            return cls._cache
        
        # 从数据库加载
        try:
            stmt = text("SELECT config_key, config_value, value_type FROM system_configs")
            result = session.execute(stmt)
            
            configs = {}
            for row in result:
                key, value, value_type = row
                configs[key] = cls._parse_value(value, value_type)
            
            cls._cache = configs
            cls._cache_timestamp = now
            logger.info(f"Loaded {len(configs)} system configs from database")
            
            return configs
            
        except Exception as e:
            logger.error(f"Failed to load system configs: {e}")
            # 返回空字典，让调用者使用默认值
            return {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（实例方法）
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        # 尝试从缓存获取
        if self._cache and key in self._cache:
            return self._cache.get(key, default)
        
        # 如果缓存为空且有 session，尝试加载
        if not self._cache and self._session:
            self.load(self._session)
        
        return self._cache.get(key, default)
    
    def get_by_prefix(self, prefix: str) -> Dict[str, Any]:
        """
        获取指定前缀的所有配置
        
        Args:
            prefix: 配置键前缀，如 'batch_decision'
            
        Returns:
            匹配前缀的配置字典 {key: value}
        """
        # 确保缓存已加载
        if not self._cache and self._session:
            self.load(self._session)
        
        result = {}
        prefix_dot = f"{prefix}."
        for key, value in self._cache.items():
            if key.startswith(prefix_dot):
                result[key] = value
        return result
    
    @classmethod
    def get_class(cls, key: str, default: Any = None, session: Session = None) -> Any:
        """
        获取配置值（类方法，用于兼容旧代码）
        
        Args:
            key: 配置键
            default: 默认值
            session: 数据库会话（如果缓存未命中）
            
        Returns:
            配置值或默认值
        """
        # 尝试从缓存获取
        if cls._cache and key in cls._cache:
            return cls._cache.get(key, default)
        
        # 如果缓存为空且提供了 session，尝试加载
        if not cls._cache and session:
            cls.load(session)
        
        return cls._cache.get(key, default)
    
    def get_int(self, key: str, default: int = 0) -> int:
        """
        获取整数配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        value = self.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = None) -> Optional[float]:
        """
        获取浮点数配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        value = self.get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """
        获取布尔配置值
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值或默认值
        """
        value = self.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
    
    @classmethod
    def get_cache_ttl(cls, data_type: str, session: Session = None) -> int:
        """
        获取缓存TTL配置
        
        Args:
            data_type: 数据类型（如 'tickers', 'ohlcv_3m'）
            session: 数据库会话
            
        Returns:
            TTL秒数
        """
        key = f"cache.ttl.{data_type}"
        return cls.get_class(key, default=300, session=session)
    
    @classmethod
    def get_all_cache_ttls(cls, session: Session = None) -> Dict[str, int]:
        """
        获取所有缓存TTL配置
        
        Returns:
            数据类型 -> TTL 的字典
        """
        if not cls._cache and session:
            cls.load(session)
        
        ttls = {}
        for key, value in cls._cache.items():
            if key.startswith('cache.ttl.'):
                data_type = key.replace('cache.ttl.', '')
                ttls[data_type] = value
        
        return ttls
    
    @classmethod
    def reload(cls, session: Session) -> Dict[str, Any]:
        """
        强制重新加载配置（绕过缓存）
        
        Args:
            session: 数据库会话
            
        Returns:
            最新配置字典
        """
        cls._cache = {}
        cls._cache_timestamp = 0
        return cls.load(session)
    
    @staticmethod
    def _parse_value(value: str, value_type: str) -> Any:
        """
        解析配置值
        
        Args:
            value: 配置值字符串
            value_type: 值类型
            
        Returns:
            解析后的值
        """
        try:
            if value_type == "integer":
                return int(value)
            elif value_type == "float":
                return float(value)
            elif value_type == "boolean":
                return value.lower() in ("true", "1", "yes", "on")
            elif value_type == "json":
                return json.loads(value)
            else:
                return value
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to parse config value '{value}' as {value_type}: {e}")
            return value


class BotConfig:
    """
    Bot 配置封装
    提供类型安全的配置访问接口
    """
    
    def __init__(self, bot):
        """
        Args:
            bot: Bot 模型实例
        """
        self.bot = bot
    
    @property
    def timeframes(self) -> List[str]:
        """获取交易时间框架列表"""
        return self.bot.trading_timeframes or ["3m", "4h"]
    
    def get_ohlcv_limit(self, timeframe: str) -> int:
        """
        获取指定时间框架的K线数量限制
        
        Args:
            timeframe: 时间框架（如 '3m', '4h'）
            
        Returns:
            K线数量限制
        """
        limits = self.bot.ohlcv_limits or {}
        return limits.get(timeframe, 100)
    
    @property
    def indicator_config(self) -> Dict:
        """获取技术指标配置"""
        return self.bot.indicator_configs or {}
    
    def get_ema_periods(self) -> List[int]:
        """获取 EMA 周期列表"""
        return self.indicator_config.get("ema_periods", [20, 50, 200])
    
    def get_rsi_period(self) -> int:
        """获取 RSI 周期"""
        return self.indicator_config.get("rsi_period", 7)
    
    def get_macd_config(self) -> Dict[str, int]:
        """获取 MACD 配置"""
        return self.indicator_config.get("macd_config", {
            "fast": 12,
            "slow": 26,
            "signal": 9
        })
    
    def get_atr_period(self) -> int:
        """获取 ATR 周期"""
        return self.indicator_config.get("atr_period", 14)
    
    def get_bollinger_config(self) -> Dict[str, float]:
        """获取布林带配置"""
        return {
            "period": self.indicator_config.get("bollinger_period", 20),
            "std": self.indicator_config.get("bollinger_std", 2.0)
        }
    
    def get_stochastic_config(self) -> Dict[str, int]:
        """获取随机指标配置"""
        return {
            "k": self.indicator_config.get("stochastic_k", 14),
            "d": self.indicator_config.get("stochastic_d", 3)
        }
    
    def get_required_ohlcv_length(self) -> int:
        """
        计算所需的最小K线数量
        基于配置的最大指标周期计算
        
        Returns:
            最小K线数量（加倍以确保充足）
        """
        ema_periods = self.get_ema_periods()
        rsi_period = self.get_rsi_period()
        macd_config = self.get_macd_config()
        macd_slow = macd_config.get("slow", 26)
        
        max_period = max(
            max(ema_periods) if ema_periods else 0,
            rsi_period,
            macd_slow
        )
        
        # 返回两倍周期以确保指标计算准确
        return max_period * 2
    
    def to_dict(self) -> Dict:
        """转换为字典（用于日志和调试）"""
        return {
            "bot_id": self.bot.id,
            "bot_name": self.bot.name,
            "timeframes": self.timeframes,
            "ohlcv_limits": {tf: self.get_ohlcv_limit(tf) for tf in self.timeframes},
            "indicator_config": self.indicator_config,
            "required_length": self.get_required_ohlcv_length()
        }

