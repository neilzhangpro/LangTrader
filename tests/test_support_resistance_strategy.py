"""支撑阻力策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.support_resistance_strategy import SupportResistanceStrategy


class TestSupportResistanceStrategy:
    """支撑阻力策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = SupportResistanceStrategy()
        
        assert strategy.name == "SupportResistanceStrategy"
        assert strategy.description == "This strategy uses the support and resistance levels to generate buy and sell signals"
    
    def test_find_pivots(self):
        """测试2：寻找支撑位和阻力位"""
        strategy = SupportResistanceStrategy()
        
        # 创建测试数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # 计算枢轴点
        pivot, support1, resistance1 = strategy.find_pivots(df)
        
        assert len(pivot) == len(df)
        assert len(support1) == len(df)
        assert len(resistance1) == len(df)
        
        # 验证类型
        assert isinstance(pivot, pd.Series)
        assert isinstance(support1, pd.Series)
        assert isinstance(resistance1, pd.Series)
        
        # 验证计算逻辑（基于测试数据）
        expected_pivot = (105 + 95 + 100) / 3  # (high + low + close) / 3
        expected_support = (2 * expected_pivot) - 105  # (2 * pivot) - high
        expected_resistance = (2 * expected_pivot) - 95  # (2 * pivot) - low
        
        assert abs(pivot.iloc[0] - expected_pivot) < 0.001
        assert abs(support1.iloc[0] - expected_support) < 0.001
        assert abs(resistance1.iloc[0] - expected_resistance) < 0.001
    
    def test_generate_signal_breakout_resistance(self):
        """测试3：突破阻力位信号"""
        strategy = SupportResistanceStrategy()
        
        # 创建突破阻力位的数据
        data = {
            'close': [100] * 19 + [110],  # 最后一个价格突破阻力位
            'high': [105] * 19 + [115],
            'low': [95] * 19 + [105],
            'open': [100] * 19 + [105],
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含支撑阻力策略信息
        assert "支撑阻力策略信号" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_breakout_support(self):
        """测试4：突破支撑位信号"""
        strategy = SupportResistanceStrategy()
        
        # 创建突破支撑位的数据
        data = {
            'close': [100] * 19 + [90],   # 最后一个价格突破支撑位
            'high': [105] * 19 + [95],
            'low': [95] * 19 + [85],
            'open': [100] * 19 + [95],
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含支撑阻力策略信息
        assert "支撑阻力策略信号" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_neutral(self):
        """测试5：中性信号"""
        strategy = SupportResistanceStrategy()
        
        # 创建中性的数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含支撑阻力策略信息
        assert "支撑阻力策略信号" in signal
        assert "价格在枢轴点附近震荡" in signal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
