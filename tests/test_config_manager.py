# tests/test_config_manager.py
"""
测试配置管理服务
"""
import pytest
from unittest.mock import MagicMock, Mock
from langtrader_core.services.config_manager import SystemConfig, BotConfig
from langtrader_core.data.models.bot import Bot


class MockSession:
    """模拟数据库会话"""
    def __init__(self, configs=None):
        self.configs = configs or []
    
    def execute(self, stmt):
        """模拟查询执行"""
        return self.configs
    
    def get(self, model, id):
        """模拟获取模型"""
        if model == Bot:
            return Bot(
                id=id,
                name="test_bot",
                exchange_id=1,
                workflow_id=1,
                llm_id=1,
                trading_timeframes=["3m", "4h"],
                ohlcv_limits={"3m": 100, "4h": 100},
                indicator_configs={
                    "ema_periods": [20, 50, 200],
                    "rsi_period": 7,
                    "macd_config": {"fast": 12, "slow": 26, "signal": 9}
                }
            )
        return None


def test_system_config_load():
    """测试系统配置加载"""
    # 清空缓存
    SystemConfig._cache = {}
    SystemConfig._cache_timestamp = 0
    
    # 模拟数据库返回
    mock_configs = [
        ('cache.ttl.tickers', '10', 'integer'),
        ('cache.ttl.ohlcv_3m', '300', 'integer'),
        ('trading.default_timeframes', '["3m", "4h"]', 'json'),
        ('system.enable_hot_reload', 'true', 'boolean'),
    ]
    
    session = MockSession(mock_configs)
    configs = SystemConfig.load(session)
    
    # 验证加载
    assert len(configs) == 4
    assert configs['cache.ttl.tickers'] == 10
    assert configs['cache.ttl.ohlcv_3m'] == 300
    assert configs['trading.default_timeframes'] == ["3m", "4h"]
    assert configs['system.enable_hot_reload'] is True


def test_system_config_get():
    """测试配置获取"""
    # 清空缓存
    SystemConfig._cache = {}
    SystemConfig._cache_timestamp = 0
    
    mock_configs = [
        ('cache.ttl.tickers', '10', 'integer'),
    ]
    
    session = MockSession(mock_configs)
    SystemConfig.load(session)
    
    # 测试获取存在的配置
    value = SystemConfig.get('cache.ttl.tickers')
    assert value == 10
    
    # 测试获取不存在的配置（返回默认值）
    value = SystemConfig.get('nonexistent.key', default=999)
    assert value == 999


def test_system_config_get_cache_ttl():
    """测试获取缓存TTL"""
    # 清空缓存
    SystemConfig._cache = {}
    SystemConfig._cache_timestamp = 0
    
    mock_configs = [
        ('cache.ttl.tickers', '10', 'integer'),
        ('cache.ttl.orderbook', '60', 'integer'),
    ]
    
    session = MockSession(mock_configs)
    SystemConfig.load(session)
    
    # 测试获取TTL
    ttl = SystemConfig.get_cache_ttl('tickers')
    assert ttl == 10
    
    ttl = SystemConfig.get_cache_ttl('orderbook')
    assert ttl == 60
    
    # 测试不存在的类型（返回默认值）
    ttl = SystemConfig.get_cache_ttl('unknown_type')
    assert ttl == 300  # 默认值


def test_system_config_get_all_cache_ttls():
    """测试获取所有缓存TTL"""
    # 清空缓存
    SystemConfig._cache = {}
    SystemConfig._cache_timestamp = 0
    
    mock_configs = [
        ('cache.ttl.tickers', '10', 'integer'),
        ('cache.ttl.orderbook', '60', 'integer'),
        ('trading.min_cycle', '180', 'integer'),  # 非缓存配置
    ]
    
    session = MockSession(mock_configs)
    SystemConfig.load(session)
    
    ttls = SystemConfig.get_all_cache_ttls()
    
    # 只返回 cache.ttl.* 的配置
    assert len(ttls) == 2
    assert ttls['tickers'] == 10
    assert ttls['orderbook'] == 60
    assert 'min_cycle' not in ttls


def test_system_config_parse_value():
    """测试配置值解析"""
    # 整数
    value = SystemConfig._parse_value('42', 'integer')
    assert value == 42
    assert isinstance(value, int)
    
    # 浮点数
    value = SystemConfig._parse_value('3.14', 'float')
    assert value == 3.14
    assert isinstance(value, float)
    
    # 布尔值
    assert SystemConfig._parse_value('true', 'boolean') is True
    assert SystemConfig._parse_value('false', 'boolean') is False
    assert SystemConfig._parse_value('1', 'boolean') is True
    assert SystemConfig._parse_value('0', 'boolean') is False
    
    # JSON
    value = SystemConfig._parse_value('["3m", "4h"]', 'json')
    assert value == ["3m", "4h"]
    assert isinstance(value, list)
    
    # 字符串
    value = SystemConfig._parse_value('test_string', 'string')
    assert value == 'test_string'


def test_system_config_caching():
    """测试配置缓存机制"""
    # 清空缓存
    SystemConfig._cache = {}
    SystemConfig._cache_timestamp = 0
    
    mock_configs = [('test.key', '123', 'integer')]
    session = MockSession(mock_configs)
    
    # 第一次加载
    configs1 = SystemConfig.load(session)
    assert len(configs1) == 1
    
    # 修改 mock 数据
    session.configs = [('test.key', '456', 'integer')]
    
    # 第二次加载（应该命中缓存，返回旧值）
    configs2 = SystemConfig.load(session)
    assert configs2['test.key'] == 123  # 缓存的旧值
    
    # 强制重新加载
    configs3 = SystemConfig.reload(session)
    assert configs3['test.key'] == 456  # 新值


def test_bot_config_timeframes():
    """测试 BotConfig 时间框架"""
    bot = Bot(
        id=1,
        name="test",
        exchange_id=1,
        workflow_id=1,
        llm_id=1,
        trading_timeframes=["5m", "1h", "4h"]
    )
    
    config = BotConfig(bot)
    assert config.timeframes == ["5m", "1h", "4h"]


def test_bot_config_ohlcv_limit():
    """测试 BotConfig OHLCV 限制"""
    bot = Bot(
        id=1,
        name="test",
        exchange_id=1,
        workflow_id=1,
        llm_id=1,
        ohlcv_limits={"3m": 150, "4h": 200}
    )
    
    config = BotConfig(bot)
    assert config.get_ohlcv_limit("3m") == 150
    assert config.get_ohlcv_limit("4h") == 200
    assert config.get_ohlcv_limit("1h") == 100  # 默认值


def test_bot_config_indicator_config():
    """测试 BotConfig 指标配置"""
    bot = Bot(
        id=1,
        name="test",
        exchange_id=1,
        workflow_id=1,
        llm_id=1,
        indicator_configs={
            "ema_periods": [10, 20, 50],
            "rsi_period": 14,
            "macd_config": {"fast": 8, "slow": 21, "signal": 5}
        }
    )
    
    config = BotConfig(bot)
    
    assert config.get_ema_periods() == [10, 20, 50]
    assert config.get_rsi_period() == 14
    
    macd = config.get_macd_config()
    assert macd["fast"] == 8
    assert macd["slow"] == 21
    assert macd["signal"] == 5


def test_bot_config_required_length():
    """测试计算所需K线长度"""
    bot = Bot(
        id=1,
        name="test",
        exchange_id=1,
        workflow_id=1,
        llm_id=1,
        indicator_configs={
            "ema_periods": [20, 50, 200],  # 最大200
            "rsi_period": 14,
            "macd_config": {"fast": 12, "slow": 26, "signal": 9}  # 最大26
        }
    )
    
    config = BotConfig(bot)
    required = config.get_required_ohlcv_length()
    
    # 应该是最大周期(200)的两倍
    assert required == 400


def test_bot_config_defaults():
    """测试默认配置"""
    bot = Bot(
        id=1,
        name="test",
        exchange_id=1,
        workflow_id=1,
        llm_id=1
        # 不设置任何动态配置
    )
    
    config = BotConfig(bot)
    
    # 应该返回默认值
    assert config.timeframes == ["3m", "4h"]
    assert config.get_ohlcv_limit("3m") == 100
    assert config.get_ema_periods() == [20, 50, 200]
    assert config.get_rsi_period() == 7


def test_bot_config_to_dict():
    """测试配置导出为字典"""
    bot = Bot(
        id=1,
        name="test_bot",
        exchange_id=1,
        workflow_id=1,
        llm_id=1,
        trading_timeframes=["3m", "4h"],
        ohlcv_limits={"3m": 100, "4h": 100}
    )
    
    config = BotConfig(bot)
    config_dict = config.to_dict()
    
    assert config_dict['bot_id'] == 1
    assert config_dict['bot_name'] == "test_bot"
    assert config_dict['timeframes'] == ["3m", "4h"]
    assert 'ohlcv_limits' in config_dict
    assert 'required_length' in config_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

