"""BBU策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.bbu_strategy import BBUStrategy


class TestBBUStrategy:
    """BBU策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = BBUStrategy()
        
        assert strategy.name == "BBUStrategy"
        assert strategy.description == "This strategy uses the BBU indicator to generate buy and sell signals"
    
    def test_generate_signal_price_above_upper_band(self):
        """测试2：价格高于上轨"""
        strategy = BBUStrategy()
        
        # 创建价格高于上轨的数据
        data = {
            'close': [100] * 19 + [110],     # 最后一个价格高于上轨
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'BBU_20_2.0_2.0': [105] * 20,    # 布林带上轨
            'BBP_20_2.0_2.0': [95] * 20      # 布林带下轨
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含BBU策略信息
        assert "布林带策略信号" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_price_below_lower_band(self):
        """测试3：价格低于下轨"""
        strategy = BBUStrategy()
        
        # 创建价格低于下轨的数据
        data = {
            'close': [100] * 19 + [90],      # 最后一个价格低于下轨
            'high': [105] * 20,
            'low': [85] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'BBU_20_2.0_2.0': [105] * 20,    # 布林带上轨
            'BBP_20_2.0_2.0': [95] * 20      # 布林带下轨
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含BBU策略信息
        assert "布林带策略信号" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_price_between_bands(self):
        """测试4：价格在布林带之间"""
        strategy = BBUStrategy()
        
        # 创建价格在布林带之间的数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'BBU_20_2.0_2.0': [105] * 20,    # 布林带上轨
            'BBP_20_2.0_2.0': [95] * 20      # 布林带下轨
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含BBU策略信息和持有信号
        assert "布林带策略信号" in signal
        assert "hold signal" in signal
        assert isinstance(signal, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
