"""增强均值回归策略测试"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.strategy.enhanced_mean_reversion_strategy import EnhancedMeanReversionStrategy


class TestEnhancedMeanReversionStrategy:
    """增强均值回归策略测试"""
    
    def test_strategy_init(self):
        """测试1：策略初始化"""
        strategy = EnhancedMeanReversionStrategy()
        
        assert strategy.name == "EnhancedMeanReversionStrategy"
        assert strategy.description == "This strategy uses the enhanced mean reversion to generate buy and sell signals"
        assert strategy.z_score_threshold == 2.0
    
    def test_calculate_z_score(self):
        """测试2：Z-Score计算"""
        strategy = EnhancedMeanReversionStrategy()
        
        # 创建测试数据
        data = {
            'close': [100, 101, 99, 102, 98, 103, 97, 104, 96, 105,
                     95, 106, 94, 107, 93, 108, 92, 109, 91, 110]
        }
        df = pd.DataFrame(data)
        
        # 计算Z-Score
        z_score = strategy.calculate_z_score(df, period=10)
        
        assert len(z_score) == len(df)
        assert isinstance(z_score, pd.Series)
        # 前10个值应该是NaN（因为周期是10）
        assert pd.isna(z_score.iloc[0])
        assert pd.isna(z_score.iloc[9])
        # 后面的值应该是数值
        assert not pd.isna(z_score.iloc[10])
    
    def test_generate_signal_overbought(self):
        """测试3：超买信号"""
        strategy = EnhancedMeanReversionStrategy()
        
        # 创建超买情况的数据
        data = {
            'close': [100] * 19 + [120],  # 最后一个价格远高于均值
            'high': [100] * 19 + [120],
            'low': [100] * 19 + [120],
            'open': [100] * 19 + [120],
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # 手动设置RSI为超买值
        with patch('src.LangTrader.strategy.enhanced_mean_reversion_strategy.ta.rsi') as mock_rsi:
            mock_rsi.return_value = pd.Series([75] * 20)  # 超买RSI
            
            # 手动设置布林带
            with patch('src.LangTrader.strategy.enhanced_mean_reversion_strategy.ta.bbands') as mock_bbands:
                mock_bbands.return_value = pd.DataFrame({
                    'BBB_20_2.0_2.0': [100] * 20,
                    'BBP_20_2.0_2.0': [100] * 20,
                    'BBU_20_2.0_2.0': [120] * 20
                })
                
                signal = strategy.generate_signal("BTC", df)
                
                assert "严重超买" in signal
                assert "Z-Score" in signal
                assert "RSI" in signal
    
    def test_generate_signal_oversold(self):
        """测试4：超卖信号"""
        strategy = EnhancedMeanReversionStrategy()
        
        # 创建超卖情况的数据
        data = {
            'close': [100] * 19 + [80],  # 最后一个价格远低于均值
            'high': [100] * 19 + [80],
            'low': [100] * 19 + [80],
            'open': [100] * 19 + [80],
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # 手动设置RSI为超卖值
        with patch('src.LangTrader.strategy.enhanced_mean_reversion_strategy.ta.rsi') as mock_rsi:
            mock_rsi.return_value = pd.Series([25] * 20)  # 超卖RSI
            
            # 手动设置布林带
            with patch('src.LangTrader.strategy.enhanced_mean_reversion_strategy.ta.bbands') as mock_bbands:
                mock_bbands.return_value = pd.DataFrame({
                    'BBB_20_2.0_2.0': [100] * 20,
                    'BBP_20_2.0_2.0': [100] * 20,
                    'BBU_20_2.0_2.0': [120] * 20
                })
                
                signal = strategy.generate_signal("BTC", df)
                
                assert "严重超卖" in signal
                assert "Z-Score" in signal
                assert "RSI" in signal
    
    def test_generate_signal_neutral(self):
        """测试5：中性信号"""
        strategy = EnhancedMeanReversionStrategy()
        
        # 创建中性情况的数据
        data = {
            'close': [100] * 20,
            'high': [100] * 20,
            'low': [100] * 20,
            'open': [100] * 20,
            'volume': [1000] * 20
        }
        df = pd.DataFrame(data)
        
        # 手动设置RSI为中性值
        with patch('src.LangTrader.strategy.enhanced_mean_reversion_strategy.ta.rsi') as mock_rsi:
            mock_rsi.return_value = pd.Series([50] * 20)  # 中性RSI
            
            # 手动设置布林带
            with patch('src.LangTrader.strategy.enhanced_mean_reversion_strategy.ta.bbands') as mock_bbands:
                mock_bbands.return_value = pd.DataFrame({
                    'BBB_20_2.0_2.0': [100] * 20,
                    'BBP_20_2.0_2.0': [100] * 20,
                    'BBU_20_2.0_2.0': [120] * 20
                })
                
                signal = strategy.generate_signal("BTC", df)
                
                assert "价格处于均值附近" in signal
                assert "Z-Score" in signal
                assert "RSI" in signal


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
