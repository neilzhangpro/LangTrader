#!/usr/bin/env python3
"""
Unit tests for QuantSignalFilter node
Tests quantitative signal filtering logic
"""
import sys
from pathlib import Path
import pytest
import pytest_asyncio

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.graph.state import State
from langtrader_core.graph.nodes.quant_signal_filter import QuantSignalFilter
from langtrader_core.plugins.registry import PluginContext
from langtrader_core.services.cache import Cache


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def default_config():
    """Default configuration for quant filter"""
    return {
        'quant_signal_weights': {
            'trend': 0.4,
            'momentum': 0.3,
            'volume': 0.2,
            'sentiment': 0.1
        },
        'quant_signal_threshold': 50
    }


@pytest.fixture
def mock_context():
    """Create mock plugin context"""
    return PluginContext(
        trader=None,
        stream_manager=None,
        database=None,
        cache=Cache(),
        rate_limiter=None,
        llm_factory=None,
        trade_history_repo=None,
        performance_service=None
    )


@pytest.fixture
def quant_filter_node(mock_context, default_config):
    """Create QuantSignalFilter node"""
    return QuantSignalFilter(context=mock_context, config=default_config)


@pytest.fixture
def bullish_indicators():
    """Indicators for a bullish market"""
    return {
        'current_price': 110,
        'kline_price': 109,
        'ema_20_3m': 105,
        'ema_20_4h': 102,
        'ema_50_4h': 98,
        'ema_200_4h': 95,
        'macd_3m': 0.5,
        'macd_4h': 0.3,
        'rsi_3m': 58,
        'rsi_4h': 55,
        'stochastic_3m': {'k': 70, 'd': 65},
        'stochastic_4h': {'k': 60, 'd': 55},
        'volume_ratio_3m': 2.0,
        'obv_3m': 5000,
        'obv_4h': 20000,
        'funding_rate': 0.0001,
    }


@pytest.fixture
def bearish_indicators():
    """Indicators for a bearish market"""
    return {
        'current_price': 90,
        'kline_price': 91,
        'ema_20_3m': 95,
        'ema_20_4h': 100,
        'ema_50_4h': 105,
        'ema_200_4h': 110,
        'macd_3m': -0.5,
        'macd_4h': -0.3,
        'rsi_3m': 35,
        'rsi_4h': 40,
        'stochastic_3m': {'k': 25, 'd': 30},
        'stochastic_4h': {'k': 30, 'd': 35},
        'volume_ratio_3m': 0.5,
        'obv_3m': -2000,
        'obv_4h': -10000,
        'funding_rate': 0.001,  # High funding rate
    }


@pytest.fixture
def neutral_indicators():
    """Indicators for a neutral/sideways market"""
    return {
        'current_price': 100,
        'kline_price': 100,
        'ema_20_3m': 100,
        'ema_20_4h': 100,
        'ema_50_4h': 100,
        'ema_200_4h': 100,
        'macd_3m': 0.0,
        'macd_4h': 0.0,
        'rsi_3m': 50,
        'rsi_4h': 50,
        'stochastic_3m': {'k': 50, 'd': 50},
        'stochastic_4h': {'k': 50, 'd': 50},
        'volume_ratio_3m': 1.0,
        'obv_3m': 0,
        'obv_4h': 0,
        'funding_rate': 0.0001,
    }


def create_state_with_indicators(symbols, indicators_map):
    """Helper to create state with given indicators"""
    market_data = {}
    for symbol in symbols:
        market_data[symbol] = {
            '3m': [],
            '4h': [],
            'indicators': indicators_map.get(symbol, {})
        }
    
    return State(
        bot_id=1,
        prompt_name='default.txt',
        symbols=symbols,
        market_data=market_data
    )


# =============================================================================
# Test Cases
# =============================================================================

class TestQuantFilterNodeCreation:
    """Test node creation and configuration"""
    
    def test_create_with_default_config(self, mock_context, default_config):
        """Test creating node with default config"""
        node = QuantSignalFilter(context=mock_context, config=default_config)
        
        assert node.weights == default_config['quant_signal_weights']
        assert node.threshold == default_config['quant_signal_threshold']
    
    def test_create_with_custom_threshold(self, mock_context):
        """Test creating node with custom threshold"""
        config = {
            'quant_signal_weights': {'trend': 0.5, 'momentum': 0.5, 'volume': 0.0, 'sentiment': 0.0},
            'quant_signal_threshold': 70
        }
        
        node = QuantSignalFilter(context=mock_context, config=config)
        
        assert node.threshold == 70


class TestQuantFilterBullishMarket:
    """Test filtering in bullish market"""
    
    @pytest.mark.asyncio
    async def test_bullish_passes_filter(self, quant_filter_node, bullish_indicators):
        """Test bullish indicators pass the filter"""
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bullish_indicators}
        )
        
        result = await quant_filter_node.run(state)
        
        assert 'BTC/USDT:USDT' in result.symbols
    
    @pytest.mark.asyncio
    async def test_quant_signal_stored_in_indicators(self, quant_filter_node, bullish_indicators):
        """Test quant signal is stored in indicators dict"""
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bullish_indicators}
        )
        
        result = await quant_filter_node.run(state)
        
        quant_signal = result.market_data['BTC/USDT:USDT']['indicators'].get('quant_signal')
        assert quant_signal is not None
        assert 'total_score' in quant_signal
        assert quant_signal['total_score'] >= 50


class TestQuantFilterBearishMarket:
    """Test filtering in bearish market"""
    
    @pytest.mark.asyncio
    async def test_bearish_filtered_out(self, quant_filter_node, bearish_indicators):
        """Test bearish indicators are filtered out"""
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bearish_indicators}
        )
        
        result = await quant_filter_node.run(state)
        
        assert 'BTC/USDT:USDT' not in result.symbols
    
    @pytest.mark.asyncio
    async def test_bearish_still_has_quant_signal(self, quant_filter_node, bearish_indicators):
        """Test quant signal is calculated even if filtered"""
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bearish_indicators}
        )
        
        await quant_filter_node.run(state)
        
        # Signal should still be stored even if filtered
        quant_signal = state.market_data['BTC/USDT:USDT']['indicators'].get('quant_signal')
        assert quant_signal is not None
        assert quant_signal['total_score'] < 50


class TestQuantFilterMixedMarket:
    """Test filtering with mixed symbols"""
    
    @pytest.mark.asyncio
    async def test_mixed_symbols_filtered(self, quant_filter_node, bullish_indicators, bearish_indicators):
        """Test that only passing symbols remain"""
        state = create_state_with_indicators(
            ['BTC/USDT:USDT', 'ETH/USDT:USDT'],
            {
                'BTC/USDT:USDT': bullish_indicators,  # Should pass
                'ETH/USDT:USDT': bearish_indicators   # Should be filtered
            }
        )
        
        result = await quant_filter_node.run(state)
        
        assert len(result.symbols) == 1
        assert 'BTC/USDT:USDT' in result.symbols
        assert 'ETH/USDT:USDT' not in result.symbols


class TestQuantFilterThreshold:
    """Test threshold variations"""
    
    @pytest.mark.asyncio
    async def test_high_threshold_filters_more(self, mock_context, bullish_indicators):
        """Test high threshold filters out more symbols"""
        # Very high threshold
        config = {
            'quant_signal_weights': {'trend': 0.4, 'momentum': 0.3, 'volume': 0.2, 'sentiment': 0.1},
            'quant_signal_threshold': 90
        }
        node = QuantSignalFilter(context=mock_context, config=config)
        
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bullish_indicators}
        )
        
        result = await node.run(state)
        
        # With 90 threshold, even bullish might not pass
        quant_signal = state.market_data['BTC/USDT:USDT']['indicators']['quant_signal']
        if quant_signal['total_score'] < 90:
            assert 'BTC/USDT:USDT' not in result.symbols
    
    @pytest.mark.asyncio
    async def test_zero_threshold_passes_all(self, mock_context, bearish_indicators):
        """Test zero threshold allows all symbols"""
        config = {
            'quant_signal_weights': {'trend': 0.4, 'momentum': 0.3, 'volume': 0.2, 'sentiment': 0.1},
            'quant_signal_threshold': 0
        }
        node = QuantSignalFilter(context=mock_context, config=config)
        
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bearish_indicators}
        )
        
        result = await node.run(state)
        
        # All symbols should pass with 0 threshold
        assert 'BTC/USDT:USDT' in result.symbols


class TestQuantFilterNoIndicators:
    """Test handling of missing data"""
    
    @pytest.mark.asyncio
    async def test_no_indicators_skipped(self, quant_filter_node):
        """Test symbols without indicators are skipped"""
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': {}}  # Empty indicators
        )
        
        result = await quant_filter_node.run(state)
        
        assert 'BTC/USDT:USDT' not in result.symbols
    
    @pytest.mark.asyncio
    async def test_missing_market_data_skipped(self, quant_filter_node):
        """Test symbols with no market data are skipped"""
        state = State(
            bot_id=1,
            symbols=['BTC/USDT:USDT'],
            market_data={}  # No market data
        )
        
        result = await quant_filter_node.run(state)
        
        assert 'BTC/USDT:USDT' not in result.symbols


class TestQuantFilterWeights:
    """Test weight customization"""
    
    @pytest.mark.asyncio
    async def test_trend_only_weights(self, mock_context, bullish_indicators):
        """Test with only trend weight"""
        config = {
            'quant_signal_weights': {'trend': 1.0, 'momentum': 0.0, 'volume': 0.0, 'sentiment': 0.0},
            'quant_signal_threshold': 50
        }
        node = QuantSignalFilter(context=mock_context, config=config)
        
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bullish_indicators}
        )
        
        await node.run(state)
        
        quant_signal = state.market_data['BTC/USDT:USDT']['indicators']['quant_signal']
        # Score should be driven entirely by trend (key is 'trend' not 'trend_score')
        assert quant_signal['breakdown']['trend'] > 0
    
    @pytest.mark.asyncio
    async def test_momentum_only_weights(self, mock_context, bullish_indicators):
        """Test with only momentum weight"""
        config = {
            'quant_signal_weights': {'trend': 0.0, 'momentum': 1.0, 'volume': 0.0, 'sentiment': 0.0},
            'quant_signal_threshold': 50
        }
        node = QuantSignalFilter(context=mock_context, config=config)
        
        state = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bullish_indicators}
        )
        
        await node.run(state)
        
        quant_signal = state.market_data['BTC/USDT:USDT']['indicators']['quant_signal']
        # Score should be driven entirely by momentum (key is 'momentum' not 'momentum_score')
        assert quant_signal['breakdown']['momentum'] > 0


class TestQuantFilterConsistency:
    """Test consistent behavior"""
    
    @pytest.mark.asyncio
    async def test_same_input_same_output(self, quant_filter_node, bullish_indicators):
        """Test deterministic output"""
        state1 = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bullish_indicators}
        )
        
        state2 = create_state_with_indicators(
            ['BTC/USDT:USDT'],
            {'BTC/USDT:USDT': bullish_indicators.copy()}
        )
        
        await quant_filter_node.run(state1)
        await quant_filter_node.run(state2)
        
        score1 = state1.market_data['BTC/USDT:USDT']['indicators']['quant_signal']['total_score']
        score2 = state2.market_data['BTC/USDT:USDT']['indicators']['quant_signal']['total_score']
        
        assert score1 == score2


class TestQuantFilterMetadata:
    """Test node metadata"""
    
    def test_node_metadata(self, quant_filter_node):
        """Test node metadata is correct"""
        meta = quant_filter_node.metadata
        
        assert meta.name == 'quant_signal_filter'
        assert 'filter' in meta.tags or 'quant' in meta.tags or 'analysis' in meta.category.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

