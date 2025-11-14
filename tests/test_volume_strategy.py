"""成交量策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.volume_strategy import VolumeStrategy


class TestVolumeStrategy:
    """成交量策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = VolumeStrategy()
        
        assert strategy.name == "VolumeStrategy"
        assert strategy.description == "This strategy uses the volume to generate buy and sell signals"
    
    def test_generate_signal_high_volume_rsi(self):
        """测试2：高成交量RSI信号"""
        strategy = VolumeStrategy()
        
        # 创建高成交量RSI的数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'volume_rsi': [80] * 20,      # 高RSI
            'volume_ratio': [1.5] * 20,   # 高成交量比率
            'volume_sma_20': [800] * 20   # SMA低于当前成交量
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含成交量策略信息
        assert "成交量策略信号" in signal
        assert "Volume RSI greater than 70" in signal
        assert "Volume ratio greater than 1" in signal
        assert "Volume SMA 20 less than volume" in signal
        assert "Volume greater than volume SMA 20" in signal
    
    def test_generate_signal_low_volume_rsi(self):
        """测试3：低成交量RSI信号"""
        strategy = VolumeStrategy()
        
        # 创建低成交量RSI的数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'volume_rsi': [20] * 20,      # 低RSI
            'volume_ratio': [0.5] * 20,   # 低成交量比率
            'volume_sma_20': [1200] * 20  # SMA高于当前成交量
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含成交量策略信息
        assert "成交量策略信号" in signal
        assert "Volume RSI less than 30" in signal
        assert "Volume ratio less than 1" in signal
        assert "Volume SMA 20 greater than volume" in signal
        assert "Volume less than volume SMA 20" in signal
    
    def test_generate_signal_neutral_volume(self):
        """测试4：中性成交量信号"""
        strategy = VolumeStrategy()
        
        # 创建中性成交量的数据
        data = {
            'close': [100] * 20,
            'high': [105] * 20,
            'low': [95] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20,
            'volume_rsi': [50] * 20,      # 中性RSI
            'volume_ratio': [1.0] * 20,   # 中性成交量比率
            'volume_sma_20': [1000] * 20  # SMA等于当前成交量
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含成交量策略信息
        assert "成交量策略信号" in signal
        assert "Volume RSI between 30 and 70" in signal
        assert "Volume ratio equal to 1" in signal
        assert "Volume SMA 20 equal to volume" in signal
        assert "Volume equal to volume SMA 20" in signal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
