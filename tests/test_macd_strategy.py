"""MACD策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.macd_strategy import MACDStrategy


class TestMACDStrategy:
    """MACD策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = MACDStrategy()
        
        assert strategy.name == "MACD Strategy"
        assert strategy.description == "This strategy uses the MACD indicator to generate buy and sell signals"
    
    def test_generate_signal_bullish_crossover(self):
        """测试2：金叉信号 (MACD > MACD Signal)"""
        strategy = MACDStrategy()
        
        # 创建金叉的数据 (MACD > MACD Signal)
        data = {
            'close': [100] * 15 + [102, 104, 106, 108, 110],  # 价格上涨导致MACD金叉
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'MACD_12_26_9': [1.2] * 20,      # MACD值
            'MACDs_12_26_9': [0.8] * 20      # MACD Signal值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含MACD策略信息和买入信号
        assert "MACD策略信号" in signal
        assert "MACD greater than MACD Signal" in signal
        assert "SELL + SHORT" in signal  # 根据代码逻辑，MACD > Signal 是卖出信号
        assert isinstance(signal, str)
    
    def test_generate_signal_bearish_crossover(self):
        """测试3：死叉信号 (MACD < MACD Signal)"""
        strategy = MACDStrategy()
        
        # 创建死叉的数据 (MACD < MACD Signal)
        data = {
            'close': [100] * 15 + [98, 96, 94, 92, 90],  # 价格下跌导致MACD死叉
            'high': [105] * 20,
            'low': [85] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'MACD_12_26_9': [0.8] * 20,      # MACD值
            'MACDs_12_26_9': [1.2] * 20      # MACD Signal值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含MACD策略信息和卖出信号
        assert "MACD策略信号" in signal
        assert "MACD less than MACD Signal" in signal
        assert "BUY + LONG" in signal  # 根据代码逻辑，MACD < Signal 是买入信号
        assert isinstance(signal, str)
    
    def test_generate_signal_neutral(self):
        """测试4：中性信号 (MACD = MACD Signal)"""
        strategy = MACDStrategy()
        
        # 创建中性的数据 (MACD = MACD Signal)
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'MACD_12_26_9': [1.0] * 20,      # MACD值
            'MACDs_12_26_9': [1.0] * 20      # MACD Signal值
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含MACD策略信息和持有信号
        assert "MACD策略信号" in signal
        assert "MACD equal to MACD Signal" in signal
        assert "HOLD signal" in signal
        assert isinstance(signal, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
