"""RSI策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.rsi_strategy import RSIStrategy


class TestRSIStrategy:
    """RSI策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = RSIStrategy()
        
        assert strategy.name == "RSI Strategy"
        assert strategy.description == "This strategy uses the RSI indicator to generate buy and sell signals"
    
    def test_generate_signal_overbought(self):
        """测试2：超买信号"""
        strategy = RSIStrategy()
        
        # 创建超买的数据 (RSI > 70)
        data = {
            'close': [100] * 14 + [105] * 6,  # 价格上涨导致RSI超买
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'RSI_14': [75] * 20  # 超买RSI值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含RSI策略信息和超买信号
        assert "RSI策略信号" in signal
        assert "RSI greater than 70" in signal
        assert "SELL + SHORT" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_oversold(self):
        """测试3：超卖信号"""
        strategy = RSIStrategy()
        
        # 创建超卖的数据 (RSI < 30)
        data = {
            'close': [100] * 14 + [95] * 6,  # 价格下跌导致RSI超卖
            'high': [105] * 20,
            'low': [90] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'RSI_14': [25] * 20  # 超卖RSI值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含RSI策略信息和超卖信号
        assert "RSI策略信号" in signal
        assert "RSI less than 30" in signal
        assert "BUY + LONG" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_neutral(self):
        """测试4：中性信号"""
        strategy = RSIStrategy()
        
        # 创建中性的数据 (30 <= RSI <= 70)
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'RSI_14': [50] * 20  # 中性RSI值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含RSI策略信息和持有信号
        assert "RSI策略信号" in signal
        assert "RSI between 30 and 70" in signal
        assert "HOLD signal" in signal
        assert isinstance(signal, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
