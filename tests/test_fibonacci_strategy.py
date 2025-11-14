"""斐波那契策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.fibonacci_strategy import FibonacciStrategy


class TestFibonacciStrategy:
    """斐波那契策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = FibonacciStrategy()
        
        assert strategy.name == "FibonacciStrategy"
        assert strategy.description == "This strategy uses the Fibonacci retracement to generate buy and sell signals"
        assert strategy.fib_levels == [0.236, 0.382, 0.5, 0.618, 0.786]
    
    def test_calculate_fibonacci_levels(self):
        """测试2：计算斐波那契回调位"""
        strategy = FibonacciStrategy()
        
        # 创建测试数据
        data = {
            'close': [100] * 10 + [90] * 10 + [110] * 10,  # 价格在90-110之间波动
            'high': [110] * 30,
            'low': [90] * 30,
            'open': [100] * 30,
            'volume': [1000] * 30
        }
        df = pd.DataFrame(data)
        
        # 计算斐波那契回调位
        fib_levels, recent_high, recent_low = strategy.calculate_fibonacci_levels(df, period=30)
        
        # 验证返回值
        assert isinstance(fib_levels, dict)
        assert len(fib_levels) == 5  # 5个斐波那契水平
        assert recent_high == 110
        assert recent_low == 90
        
        # 验证斐波那契水平计算
        price_range = 110 - 90  # 20
        for level, price in fib_levels.items():
            expected_price = 110 - (price_range * level)
            assert abs(price - expected_price) < 0.001
    
    def test_generate_signal_near_fib_level(self):
        """测试3：价格接近斐波那契回调位信号"""
        strategy = FibonacciStrategy()
        
        # 创建价格接近斐波那契回调位的数据
        data = {
            'close': [100] * 29 + [102.36],  # 接近0.382回调位(110-(20*0.382)=102.36)
            'high': [110] * 30,
            'low': [90] * 30,
            'open': [100] * 30,
            'volume': [1000] * 30
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含斐波那契策略信息
        assert "斐波那契策略信号" in signal
        assert isinstance(signal, str)
    
    def test_generate_signal_no_fib_signal(self):
        """测试4：无斐波那契信号"""
        strategy = FibonacciStrategy()
        
        # 创建无斐波那契信号的数据
        data = {
            'close': [100] * 30,
            'high': [110] * 30,
            'low': [90] * 30,
            'open': [100] * 30,
            'volume': [1000] * 30
        }
        df = pd.DataFrame(data)
        
        signal = strategy.generate_signal("BTC", df)
        
        # 验证信号包含斐波那契策略信息
        assert "斐波那契策略信号" in signal
        assert isinstance(signal, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
