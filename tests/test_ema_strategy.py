"""EMA策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.ema_strategy import EMA20Strategy


class TestEMA20Strategy:
    """EMA20策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = EMA20Strategy()
        
        assert strategy.name == "EMA20Strategy"
        assert strategy.description == "This strategy uses the EMA20 indicator to generate buy and sell signals"
    
    def test_generate_signal_price_above_sma(self):
        """测试2：价格高于SMA"""
        strategy = EMA20Strategy()
        
        # 创建价格高于SMA的数据
        data = {
            'close': [100] * 19 + [105],   # 最后一个价格高于SMA
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'SMA_20': [100] * 20,          # SMA值
            'EMA_20': [98] * 20            # EMA值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含EMA20策略信息和卖出信号
        assert "EMA20策略信号" in signal
        assert "SMA greater than current price" in signal
        assert "sell signal" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_price_below_ema(self):
        """测试3：价格低于EMA"""
        strategy = EMA20Strategy()
        
        # 创建价格低于EMA的数据
        data = {
            'close': [100] * 19 + [95],    # 最后一个价格低于EMA
            'high': [105] * 20,
            'low': [90] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'SMA_20': [102] * 20,          # SMA值
            'EMA_20': [100] * 20           # EMA值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含EMA20策略信息和买入信号
        assert "EMA20策略信号" in signal
        assert "EMA less than current price" in signal
        assert "buy signal" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_price_between_sma_ema(self):
        """测试4：价格在SMA和EMA之间"""
        strategy = EMA20Strategy()
        
        # 创建价格在SMA和EMA之间的数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'SMA_20': [101] * 20,          # SMA值
            'EMA_20': [99] * 20            # EMA值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含EMA20策略信息和持有信号
        assert "EMA20策略信号" in signal
        assert "SMA and EMA between" in signal
        assert "hold signal" in signal
        assert isinstance(signal, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
