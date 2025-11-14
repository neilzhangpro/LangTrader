"""一目均衡表策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.ichimoku_strategy import IchimokuStrategy


class TestIchimokuStrategy:
    """一目均衡表策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = IchimokuStrategy()
        
        assert strategy.name == "IchimokuStrategy"
        assert strategy.description == "This strategy uses the Ichimoku indicator to generate buy and sell signals"
    
    def test_calculate_ichimoku(self):
        """测试2：一目均衡表指标计算"""
        strategy = IchimokuStrategy()
        
        # 创建测试数据
        data = {
            'close': [100] * 52,
            'high': [105] * 52,
            'low': [95] * 52,
            'open': [100] * 52,
            'volume': [1000] * 52
        }
        df = pd.DataFrame(data)
        
        # 计算一目均衡表指标
        tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span = strategy.calculate_ichimoku(df)
        
        assert len(tenkan_sen) == len(df)
        assert len(kijun_sen) == len(df)
        assert len(senkou_span_a) == len(df)
        assert len(senkou_span_b) == len(df)
        assert len(chikou_span) == len(df)
        
        # 验证类型
        assert isinstance(tenkan_sen, pd.Series)
        assert isinstance(kijun_sen, pd.Series)
        assert isinstance(senkou_span_a, pd.Series)
        assert isinstance(senkou_span_b, pd.Series)
        assert isinstance(chikou_span, pd.Series)
    
    def test_generate_signal_bullish(self):
        """测试3：强势买入信号"""
        strategy = IchimokuStrategy()
        
        # 创建强势买入的数据
        data = {
            'close': [100] * 51 + [110],  # 最后一个价格大幅上涨
            'high': [105] * 51 + [115],
            'low': [95] * 51 + [105],
            'open': [100] * 51 + [105],
            'volume': [1000] * 52
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含一目均衡表信息
        assert "一目均衡表策略信号" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_bearish(self):
        """测试4：强势卖出信号"""
        strategy = IchimokuStrategy()
        
        # 创建强势卖出的数据
        data = {
            'close': [100] * 51 + [90],   # 最后一个价格大幅下跌
            'high': [105] * 51 + [95],
            'low': [95] * 51 + [85],
            'open': [100] * 51 + [95],
            'volume': [1000] * 52
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含一目均衡表信息
        assert "一目均衡表策略信号" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_neutral(self):
        """测试5：中性信号"""
        strategy = IchimokuStrategy()
        
        # 创建中性的数据
        data = {
            'close': [100] * 52,
            'high': [105] * 52,
            'low': [95] * 52,
            'open': [100] * 52,
            'volume': [1000] * 52
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含一目均衡表信息
        assert "一目均衡表策略信号" in signal
        assert "无明确一目均衡表信号" in signal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
