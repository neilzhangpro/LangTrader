"""基础策略类测试"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.base_strategy import BaseStrategy


class TestBaseStrategy:
    """基础策略类测试"""
    
    def test_base_strategy_init(self):
        """测试1：基础策略初始化"""
        strategy = BaseStrategy("TestStrategy", "This is a test strategy")
        
        assert strategy.name == "TestStrategy"
        assert strategy.description == "This is a test strategy"
    
    def test_base_strategy_abstract_method(self):
        """测试2：抽象方法未实现"""
        # 直接实例化抽象类应该抛出TypeError
        with pytest.raises(TypeError):
            BaseStrategy("Test", "Test description")
    
    def test_base_strategy_inheritance(self):
        """测试3：继承基础策略"""
        # 创建一个具体的策略类来测试继承
        class ConcreteStrategy(BaseStrategy):
            def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
                return f"Signal for {symbol}"
        
        strategy = ConcreteStrategy("Concrete", "Concrete strategy")
        
        assert strategy.name == "Concrete"
        assert strategy.description == "Concrete strategy"
        
        # 测试generate_signal方法
        df = pd.DataFrame({'close': [100, 101, 102]})
        signal = strategy.generate_signal("BTC", df)
        
        assert signal == "Signal for BTC"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
