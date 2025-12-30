#!/usr/bin/env python3
"""
Pytest fixtures for LangTrader unit tests
Provides shared test data and mock objects
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any
import pytest
import pytest_asyncio

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.graph.state import (
    State, Account, Position, AIDecision, ExecutionResult, RunRecord
)
from langtrader_core.backtest.mock_trader import MockTrader, BacktestDataSource
from langtrader_core.backtest.mock_performance import MockPerformanceService
from langtrader_core.services.indicators import Kline


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_ohlcv_data() -> List[List]:
    """
    Generate sample OHLCV data for testing
    Format: [timestamp, open, high, low, close, volume]
    """
    base_time = int(datetime(2024, 1, 1, 0, 0, 0).timestamp() * 1000)
    interval_ms = 3 * 60 * 1000  # 3 minutes
    
    data = []
    price = 100.0
    
    for i in range(200):  # 200 candles
        timestamp = base_time + (i * interval_ms)
        # Simulate price movement
        change = (i % 10 - 5) * 0.5  # Oscillate between -2.5 and +2.5
        open_price = price
        close_price = price + change
        high_price = max(open_price, close_price) + abs(change) * 0.2
        low_price = min(open_price, close_price) - abs(change) * 0.2
        volume = 1000 + (i % 20) * 100
        
        data.append([timestamp, open_price, high_price, low_price, close_price, volume])
        price = close_price
    
    return data


@pytest.fixture
def sample_klines(sample_ohlcv_data) -> List[Kline]:
    """Convert OHLCV data to Kline objects"""
    return [
        Kline(
            open_time=k[0],
            open=k[1],
            high=k[2],
            low=k[3],
            close=k[4],
            volume=k[5],
            close_time=k[0],
            quote_volume=k[4] * k[5],
            trades=100
        )
        for k in sample_ohlcv_data
    ]


@pytest.fixture
def sample_indicators() -> Dict[str, Any]:
    """Realistic indicator values for testing"""
    return {
        'current_price': 105.0,
        'kline_price': 104.8,
        'ema_20_3m': 103.5,
        'ema_20_4h': 102.0,
        'ema_50_4h': 100.0,
        'ema_200_4h': 98.0,
        'macd_3m': 0.5,
        'macd_4h': 0.3,
        'rsi_3m': 55.0,
        'rsi_4h': 58.0,
        'atr_3m': 1.5,
        'atr_4h': 3.0,
        'volume_ratio_3m': 1.5,
        'obv_3m': 5000.0,
        'obv_4h': 25000.0,
        'stochastic_3m': {'k': 65, 'd': 60},
        'stochastic_4h': {'k': 55, 'd': 50},
        'bollinger_3m': {'upper': 110, 'middle': 105, 'lower': 100, 'bandwidth': 0.095, 'percent_b': 0.5},
        'bollinger_4h': {'upper': 112, 'middle': 104, 'lower': 96, 'bandwidth': 0.154, 'percent_b': 0.56},
        'adx_4h': {'adx': 25, 'plus_di': 30, 'minus_di': 20},
        'vwap_3m': 104.5,
        'atr_percent_3m': 1.43,
        'atr_percent_4h': 2.88,
        'funding_rate': 0.0001,
    }


# =============================================================================
# Mock Data Source
# =============================================================================

class InMemoryDataSource(BacktestDataSource):
    """In-memory data source for testing without exchange connection"""
    
    def __init__(self, ohlcv_data: Dict[str, Dict[str, List[List]]], start_time: datetime, end_time: datetime):
        super().__init__(start_time, end_time, cache=None)
        self.preloaded_data = ohlcv_data
        self.markets = {
            'BTC/USDT:USDT': {'symbol': 'BTC/USDT:USDT', 'active': True, 'swap': True},
            'ETH/USDT:USDT': {'symbol': 'ETH/USDT:USDT', 'active': True, 'swap': True},
        }
    
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[List]:
        """Get OHLCV filtered by current_time"""
        if symbol not in self.preloaded_data:
            return []
        
        all_data = self.preloaded_data.get(symbol, {}).get(timeframe, [])
        
        # Filter by current_time
        filtered = [candle for candle in all_data if candle[0] <= self.current_time]
        
        return filtered[-limit:] if len(filtered) >= limit else filtered
    
    async def get_funding_rates(self, symbols: List[str]) -> Dict[str, float]:
        """Return mock funding rates"""
        return {symbol: 0.0001 for symbol in symbols}
    
    async def get_markets(self) -> Dict:
        """Return mock markets"""
        return self.markets


@pytest.fixture
def mock_data_source(sample_ohlcv_data) -> InMemoryDataSource:
    """Create in-memory data source with sample data"""
    start_time = datetime(2024, 1, 1, 0, 0, 0)
    end_time = datetime(2024, 1, 1, 10, 0, 0)
    
    # Create data for multiple symbols
    data = {
        'BTC/USDT:USDT': {
            '3m': sample_ohlcv_data,
            '4h': sample_ohlcv_data[:50],  # Less 4h data
        },
        'ETH/USDT:USDT': {
            '3m': sample_ohlcv_data,
            '4h': sample_ohlcv_data[:50],
        },
    }
    
    source = InMemoryDataSource(data, start_time, end_time)
    # Set current_time to middle of dataset
    source.current_time = int(datetime(2024, 1, 1, 5, 0, 0).timestamp() * 1000)
    
    return source


# =============================================================================
# MockTrader Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def mock_trader(mock_data_source) -> MockTrader:
    """Create MockTrader with in-memory data source"""
    performance = MockPerformanceService()
    
    trader = MockTrader(
        initial_balance=10000.0,
        data_source=mock_data_source,
        commission=0.0005,
        slippage=0.0002,
        performance_service=performance
    )
    
    # Initialize markets
    trader.markets = await mock_data_source.get_markets()
    
    return trader


@pytest.fixture
def mock_performance() -> MockPerformanceService:
    """Create MockPerformanceService for testing"""
    return MockPerformanceService()


# =============================================================================
# State Fixtures
# =============================================================================

@pytest.fixture
def sample_account() -> Account:
    """Sample account for testing"""
    return Account(
        timestamp=datetime.now(),
        free={'USDT': 10000.0},
        used={'USDT': 0.0},
        total={'USDT': 10000.0},
        debt={'USDT': 0.0}
    )


@pytest.fixture
def sample_position() -> Position:
    """Sample position for testing"""
    return Position(
        id='test_position_1',
        symbol='BTC/USDT:USDT',
        side='buy',
        type='market',
        status='open',
        datetime=datetime.now(),
        price=100.0,
        average=100.0,
        amount=1.0,
        stop_loss_price=95.0,
        take_profit_price=110.0
    )


@pytest.fixture
def sample_decision() -> AIDecision:
    """Sample AI decision for testing"""
    return AIDecision(
        symbol='BTC/USDT:USDT',
        action='open_long',
        leverage=2,
        position_size_usd=500.0,
        stop_loss_price=95.0,
        take_profit_price=110.0,
        confidence=0.75,
        risk_usd=25.0,
        reasons=['Strong uptrend', 'RSI in neutral zone']
    )


@pytest.fixture
def sample_state(sample_account, sample_indicators) -> State:
    """Sample state for testing nodes"""
    state = State(
        bot_id=1,
        prompt_name='default.txt',
        initial_balance=10000.0,
        symbols=['BTC/USDT:USDT', 'ETH/USDT:USDT'],
        account=sample_account,
        positions=[],
        market_data={
            'BTC/USDT:USDT': {
                '3m': [],  # Would be filled with OHLCV
                '4h': [],
                'indicators': sample_indicators
            },
            'ETH/USDT:USDT': {
                '3m': [],
                '4h': [],
                'indicators': sample_indicators.copy()
            }
        },
        runs={}
    )
    return state


# =============================================================================
# Plugin Context Fixture
# =============================================================================

@pytest.fixture
def mock_plugin_context(mock_trader, mock_performance):
    """Create mock plugin context for testing nodes"""
    from langtrader_core.plugins.registry import PluginContext
    from langtrader_core.services.cache import Cache
    from langtrader_core.services.ratelimit import RateLimiter
    
    return PluginContext(
        trader=mock_trader,
        stream_manager=None,  # No stream manager in tests
        database=None,
        cache=Cache(),
        rate_limiter=RateLimiter(),
        llm_factory=None,
        trade_history_repo=None,
        performance_service=mock_performance
    )

