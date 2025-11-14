"""波动率突破策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.volatility_breakout_strategy import VolatilityBreakoutStrategy


class TestVolatilityBreakoutStrategy:
    """波动率突破策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = VolatilityBreakoutStrategy()
        
        assert strategy.name == "VolatilityBreakoutStrategy"
        assert strategy.description == "This strategy uses the volatility breakout to generate buy and sell signals"
        assert strategy.period == 14
        assert strategy.multiplier == 2
        assert strategy.atr_period == 14
    
    def test_generate_signal_breakout_up(self):
        """测试2：向上突破信号"""
        strategy = VolatilityBreakoutStrategy()
        
        # 创建向上突破的数据
        data = {
            'close': [100] * 18 + [105, 110],  # 最后两个价格上涨
            'high': [100] * 18 + [105, 115],   # 最高价突破
            'low': [100] * 18 + [95, 105],
            'open': [100] * 18 + [100, 105],
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # 模拟ATR计算
        with patch('src.LangTrader.strategy.volatility_breakout_strategy.ta.atr') as mock_atr:
            mock_atr.return_value = pd.Series([5] * 20)  # ATR为5
            
            signal = strategy.generate_signal("BTC", df)
            
            # 验证信号包含突破信息
            assert "波动突破策略信号" in signal
            assert isinstance(signal, str)
    
    def test_generate_signal_breakout_down(self):
        """测试3：向下突破信号"""
        strategy = VolatilityBreakoutStrategy()
        
        # 创建向下突破的数据
        data = {
            'close': [100] * 18 + [95, 90],   # 最后两个价格下跌
            'high': [100] * 18 + [105, 95],
            'low': [100] * 18 + [95, 85],     # 最低价突破
            'open': [100] * 18 + [100, 95],
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # 模拟ATR计算
        with patch('src.LangTrader.strategy.volatility_breakout_strategy.ta.atr') as mock_atr:
            mock_atr.return_value = pd.Series([5] * 20)  # ATR为5
            
            signal = strategy.generate_signal("BTC", df)
            
            # 验证信号包含突破信息
            assert "波动突破策略信号" in signal
            assert isinstance(signal, str)
    
    def test_generate_signal_no_breakout(self):
        """测试4：无突破信号"""
        strategy = VolatilityBreakoutStrategy()
        
        # 创建无突破的数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # 模拟ATR计算
        with patch('src.LangTrader.strategy.volatility_breakout_strategy.ta.atr') as mock_atr:
            mock_atr.return_value = pd.Series([5] * 20)  # ATR为5
            
            signal = strategy.generate_signal("BTC", df)
            
            # 验证信号包含无突破信息
            assert "价格未突破波动率轨道" in signal
    
    def test_generate_signal_atr_none(self):
        """测试5：ATR为None的情况"""
        strategy = VolatilityBreakoutStrategy()
        
        # 创建测试数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # 模拟ATR为None
        with patch('src.LangTrader.strategy.volatility_breakout_strategy.ta.atr') as mock_atr:
            mock_atr.return_value = None
            
            signal = strategy.generate_signal("BTC", df)
            
            # 验证处理了ATR为None的情况
            assert "ATR is None or length is 0" in signal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
