# tests/test_market_metrics.py
"""
测试市场深度指标（订单簿和成交记录）
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langtrader_core.services.market import Market
from langtrader_core.services.cache import Cache
from langtrader_core.services.ratelimit import RateLimiter


class MockTrader:
    """模拟交易者（用于测试）"""
    def __init__(self, exchange=None):
        self.exchange = exchange or MockExchange()


class MockExchange:
    """模拟交易所（用于测试）"""
    def __init__(self):
        self.rateLimit = 50
        self.id = 'binance'
    
    async def fetch_order_book(self, symbol, limit=20):
        """模拟订单簿数据"""
        return {
            'bids': [
                [50000, 1.0],   # [price, amount]
                [49950, 2.0],
                [49900, 1.5],
                [49850, 1.2],
                [49800, 0.8],
                [49750, 1.1],
                [49700, 0.9],
                [49650, 1.3],
                [49600, 1.0],
                [49550, 0.7],
            ],
            'asks': [
                [50100, 0.8],
                [50150, 1.5],
                [50200, 1.2],
                [50250, 1.0],
                [50300, 0.9],
                [50350, 1.1],
                [50400, 0.7],
                [50450, 1.3],
                [50500, 1.0],
                [50550, 0.8],
            ]
        }
    
    async def fetch_trades(self, symbol, limit=100):
        """模拟成交记录"""
        base_time = 1609459200000  # 2021-01-01 00:00:00
        trades = []
        
        # 生成100笔交易，买单60笔，卖单40笔（买盘强）
        for i in range(100):
            side = 'buy' if i < 60 else 'sell'
            trades.append({
                'timestamp': base_time + i * 1000,  # 每秒一笔
                'price': 50000 + (i * 10),  # 价格逐渐上涨
                'amount': 0.1 + (i % 5) * 0.02,  # 0.1-0.18 BTC
                'side': side
            })
        
        return trades


@pytest.fixture
def mock_market():
    """创建测试用的Market实例"""
    trader = MockTrader()
    cache = Cache()
    # 清空缓存（因为Cache是单例，需要清理之前测试的数据）
    cache.cache.clear()
    rate_limiter = RateLimiter()
    market = Market(
        trader=trader,
        stream_manager=MagicMock(),  # 非None表示实盘模式
        cache=cache,
        rate_limiter=rate_limiter
    )
    return market


@pytest.fixture
def mock_market_backtest():
    """创建回测模式的Market实例"""
    trader = MockTrader()
    cache = Cache()
    # 清空缓存（因为Cache是单例，需要清理之前测试的数据）
    cache.cache.clear()
    rate_limiter = RateLimiter()
    market = Market(
        trader=trader,
        stream_manager=None,  # None表示回测模式
        cache=cache,
        rate_limiter=rate_limiter
    )
    return market


@pytest.mark.asyncio
async def test_order_book_metrics_calculation(mock_market):
    """测试订单簿指标计算"""
    symbols = ['BTC/USDT:USDT']
    metrics = await mock_market._fetch_order_book_metrics(symbols)
    
    assert 'BTC/USDT:USDT' in metrics
    symbol_metrics = metrics['BTC/USDT:USDT']
    
    # 检查所有必需的指标
    assert 'spread' in symbol_metrics
    assert 'imbalance' in symbol_metrics
    assert 'liquidity_depth' in symbol_metrics
    assert 'bid_volume_10' in symbol_metrics
    assert 'ask_volume_10' in symbol_metrics
    
    # 验证spread计算正确（bid=50000, ask=50100）
    expected_spread = (50100 - 50000) / 50000
    assert abs(symbol_metrics['spread'] - expected_spread) < 0.0001
    
    # 验证liquidity_depth是前10档的总和
    expected_bid_volume = 1.0 + 2.0 + 1.5 + 1.2 + 0.8 + 1.1 + 0.9 + 1.3 + 1.0 + 0.7
    expected_ask_volume = 0.8 + 1.5 + 1.2 + 1.0 + 0.9 + 1.1 + 0.7 + 1.3 + 1.0 + 0.8
    
    assert abs(symbol_metrics['bid_volume_10'] - expected_bid_volume) < 0.01
    assert abs(symbol_metrics['ask_volume_10'] - expected_ask_volume) < 0.01
    
    # 验证imbalance在-1到1之间
    assert -1 <= symbol_metrics['imbalance'] <= 1
    
    # 由于买单总量(11.5) > 卖单总量(10.3)，imbalance应该>0
    assert symbol_metrics['imbalance'] > 0


@pytest.mark.asyncio
async def test_trade_metrics_calculation(mock_market):
    """测试成交记录指标计算"""
    symbols = ['BTC/USDT:USDT']
    metrics = await mock_market._fetch_trade_metrics(symbols)
    
    assert 'BTC/USDT:USDT' in metrics
    symbol_metrics = metrics['BTC/USDT:USDT']
    
    # 检查所有必需的指标
    assert 'buy_sell_ratio' in symbol_metrics
    assert 'trade_intensity' in symbol_metrics
    assert 'avg_trade_size' in symbol_metrics
    assert 'price_momentum' in symbol_metrics
    
    # 验证buy_sell_ratio (60买:40卖 = 1.5)
    # 实际计算需要考虑每笔交易的amount
    assert symbol_metrics['buy_sell_ratio'] > 1.0  # 买盘应该更强
    
    # 验证trade_intensity (100笔/100秒 ≈ 1笔/秒)
    assert 0.8 < symbol_metrics['trade_intensity'] < 1.2
    
    # 验证price_momentum为正（价格上涨）
    assert symbol_metrics['price_momentum'] > 0


@pytest.mark.asyncio
async def test_backtest_mode_skips_metrics(mock_market_backtest):
    """测试回测模式跳过新指标"""
    symbols = ['BTC/USDT:USDT']
    
    # 回测模式应该返回空字典
    order_book_metrics = await mock_market_backtest._fetch_order_book_metrics(symbols)
    assert order_book_metrics == {}
    
    trade_metrics = await mock_market_backtest._fetch_trade_metrics(symbols)
    assert trade_metrics == {}


@pytest.mark.asyncio
async def test_cache_functionality(mock_market):
    """测试缓存功能"""
    symbols = ['BTC/USDT:USDT']
    
    # 第一次调用 - 应该从API获取
    metrics1 = await mock_market._fetch_order_book_metrics(symbols)
    assert 'BTC/USDT:USDT' in metrics1
    
    # 检查缓存中是否存在
    cached_data = mock_market.cache.get('orderbook', 'BTC/USDT:USDT')
    assert cached_data is not None
    assert cached_data == metrics1['BTC/USDT:USDT']
    
    # 第二次调用 - 应该从缓存获取（在60秒内）
    metrics2 = await mock_market._fetch_order_book_metrics(symbols)
    assert metrics2 == metrics1


@pytest.mark.asyncio
async def test_error_handling_order_book(mock_market):
    """测试订单簿API错误处理"""
    # 模拟API错误
    mock_market.trader.exchange.fetch_order_book = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    symbols = ['BTC/USDT:USDT']
    metrics = await mock_market._fetch_order_book_metrics(symbols)
    
    # 错误时应该返回空字典，而不是抛出异常
    assert metrics == {}


@pytest.mark.asyncio
async def test_error_handling_trades(mock_market):
    """测试成交记录API错误处理"""
    # 模拟API错误
    mock_market.trader.exchange.fetch_trades = AsyncMock(
        side_effect=Exception("API Error")
    )
    
    symbols = ['BTC/USDT:USDT']
    metrics = await mock_market._fetch_trade_metrics(symbols)
    
    # 错误时应该返回空字典
    assert metrics == {}


@pytest.mark.asyncio
async def test_empty_order_book_handling(mock_market):
    """测试空订单簿处理"""
    # 模拟空订单簿
    mock_market.trader.exchange.fetch_order_book = AsyncMock(
        return_value={'bids': [], 'asks': []}
    )
    
    symbols = ['BTC/USDT:USDT']
    metrics = await mock_market._fetch_order_book_metrics(symbols)
    
    # 空订单簿应该被跳过
    assert 'BTC/USDT:USDT' not in metrics


@pytest.mark.asyncio
async def test_insufficient_trades_handling(mock_market):
    """测试交易数据不足的处理"""
    # 模拟只有5笔交易（少于10笔）
    mock_market.trader.exchange.fetch_trades = AsyncMock(
        return_value=[
            {'timestamp': 1000, 'price': 50000, 'amount': 0.1, 'side': 'buy'}
            for _ in range(5)
        ]
    )
    
    symbols = ['BTC/USDT:USDT']
    metrics = await mock_market._fetch_trade_metrics(symbols)
    
    # 交易数据不足应该被跳过
    assert 'BTC/USDT:USDT' not in metrics


@pytest.mark.asyncio
async def test_multiple_symbols(mock_market):
    """测试多个交易对"""
    symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT']
    
    order_book_metrics = await mock_market._fetch_order_book_metrics(symbols)
    
    # 应该为每个symbol都获取指标
    assert len(order_book_metrics) == 2
    assert 'BTC/USDT:USDT' in order_book_metrics
    assert 'ETH/USDT:USDT' in order_book_metrics


@pytest.mark.asyncio
async def test_order_book_imbalance_calculation():
    """测试订单簿不平衡度计算逻辑"""
    # 测试买盘强的情况
    bid_volume = 100
    ask_volume = 50
    total = bid_volume + ask_volume
    imbalance = (bid_volume - ask_volume) / total
    
    assert imbalance == pytest.approx(0.333, abs=0.01)
    assert imbalance > 0  # 买盘强
    
    # 测试卖盘强的情况
    bid_volume = 50
    ask_volume = 100
    total = bid_volume + ask_volume
    imbalance = (bid_volume - ask_volume) / total
    
    assert imbalance == pytest.approx(-0.333, abs=0.01)
    assert imbalance < 0  # 卖盘强
    
    # 测试平衡情况
    bid_volume = 100
    ask_volume = 100
    total = bid_volume + ask_volume
    imbalance = (bid_volume - ask_volume) / total
    
    assert imbalance == 0  # 平衡


@pytest.mark.asyncio
async def test_rate_limiter_called(mock_market):
    """测试限流器被正确调用"""
    # 使用spy模式监控rate_limiter
    with patch.object(mock_market.rate_limiter, 'wait_if_needed', new_callable=AsyncMock) as mock_wait:
        symbols = ['BTC/USDT:USDT']
        await mock_market._fetch_order_book_metrics(symbols)
        
        # 限流器应该被调用
        assert mock_wait.call_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

