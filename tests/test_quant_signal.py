#!/usr/bin/env python3
"""
量化信号计算单元测试
"""
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.services.quant_signal import QuantSignalCalculator


def test_trend_score():
    """测试趋势得分计算"""
    print("\n=== Test Trend Score ===")
    
    # 测试多头趋势
    indicators = {
        'current_price': 110,
        'ema_20_3m': 105,
        'ema_20_4h': 100,
        'ema_50_4h': 95,
        'ema_200_4h': 90
    }
    
    result = QuantSignalCalculator.calculate_trend_score(indicators)
    print(f"Bullish Trend Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] > 50, "Bullish trend should have score > 50"
    
    # 测试空头趋势
    indicators = {
        'current_price': 90,
        'ema_20_3m': 95,
        'ema_20_4h': 100,
        'ema_50_4h': 105,
        'ema_200_4h': 110
    }
    
    result = QuantSignalCalculator.calculate_trend_score(indicators)
    print(f"Bearish Trend Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] < 50, "Bearish trend should have score < 50"
    
    print("✅ Trend score test passed")


def test_momentum_score():
    """测试动量得分计算"""
    print("\n=== Test Momentum Score ===")
    
    # 测试强势动量
    indicators = {
        'macd_3m': 0.5,
        'macd_4h': 0.3,
        'rsi_3m': 55,
        'rsi_4h': 60,
        'stochastic_3m': {'k': 70, 'd': 65}
    }
    
    result = QuantSignalCalculator.calculate_momentum_score(indicators)
    print(f"Strong Momentum Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] > 70, "Strong momentum should have high score"
    
    # 测试超买状态
    indicators = {
        'macd_3m': 0.5,
        'macd_4h': 0.3,
        'rsi_3m': 85,
        'rsi_4h': 82,
        'stochastic_3m': {'k': 70, 'd': 65}
    }
    
    result = QuantSignalCalculator.calculate_momentum_score(indicators)
    print(f"Overbought Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] <= 60, "Overbought should reduce score"
    
    print("✅ Momentum score test passed")


def test_volume_score():
    """测试量能得分计算"""
    print("\n=== Test Volume Score ===")
    
    # 测试放量
    indicators = {
        'volume_ratio_3m': 2.5,
        'obv_3m': 1000,
        'obv_4h': 5000
    }
    
    result = QuantSignalCalculator.calculate_volume_score(indicators)
    print(f"High Volume Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] > 70, "High volume should have high score"
    
    # 测试缩量
    indicators = {
        'volume_ratio_3m': 0.5,
        'obv_3m': 100,
        'obv_4h': 200
    }
    
    result = QuantSignalCalculator.calculate_volume_score(indicators)
    print(f"Low Volume Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] <= 50, "Low volume should reduce score"
    
    print("✅ Volume score test passed")


def test_sentiment_score():
    """测试市场情绪得分计算"""
    print("\n=== Test Sentiment Score ===")
    
    # 测试健康资金费率
    indicators = {'funding_rate': 0.03}
    result = QuantSignalCalculator.calculate_sentiment_score(indicators)
    print(f"Healthy Funding Rate Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] >= 70, "Healthy funding should have good score"
    
    # 测试极端高资金费率
    indicators = {'funding_rate': 0.15}
    result = QuantSignalCalculator.calculate_sentiment_score(indicators)
    print(f"Extreme High Funding Rate Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] <= 40, "Extreme funding should have low score"
    
    # 测试负资金费率（做多机会）
    indicators = {'funding_rate': -0.08}
    result = QuantSignalCalculator.calculate_sentiment_score(indicators)
    print(f"Negative Funding Rate Score: {result['score']}")
    print(f"Reasons: {result['reasons']}")
    assert result['score'] >= 70, "Negative funding should be opportunity"
    
    print("✅ Sentiment score test passed")


def test_composite_score():
    """测试综合得分计算"""
    print("\n=== Test Composite Score ===")
    
    # 测试强势信号
    indicators = {
        'current_price': 110,
        'ema_20_3m': 105,
        'ema_20_4h': 100,
        'ema_50_4h': 95,
        'ema_200_4h': 90,
        'macd_3m': 0.5,
        'macd_4h': 0.3,
        'rsi_3m': 55,
        'rsi_4h': 60,
        'stochastic_3m': {'k': 70, 'd': 65},
        'volume_ratio_3m': 2.0,
        'obv_3m': 1000,
        'obv_4h': 5000,
        'funding_rate': 0.03
    }
    
    weights = {
        "trend": 0.4,
        "momentum": 0.3,
        "volume": 0.2,
        "sentiment": 0.1
    }
    
    result = QuantSignalCalculator.calculate_composite_score(indicators, weights)
    print(f"Strong Signal Composite Score: {result['total_score']}")
    print(f"Breakdown: {result['breakdown']}")
    print(f"All Reasons: {result['reasons']}")
    assert result['total_score'] > 70, "Strong signal should have high composite score"
    assert result['pass_filter'], "Strong signal should pass filter"
    
    # 测试弱势信号
    indicators = {
        'current_price': 90,
        'ema_20_3m': 95,
        'ema_20_4h': 100,
        'ema_50_4h': 100,
        'ema_200_4h': 100,
        'macd_3m': -0.2,
        'macd_4h': -0.1,
        'rsi_3m': 85,
        'rsi_4h': 82,
        'stochastic_3m': {'k': 30, 'd': 35},
        'volume_ratio_3m': 0.5,
        'obv_3m': -500,
        'obv_4h': -1000,
        'funding_rate': 0.15
    }
    
    result = QuantSignalCalculator.calculate_composite_score(indicators, weights)
    print(f"Weak Signal Composite Score: {result['total_score']}")
    print(f"Breakdown: {result['breakdown']}")
    assert result['total_score'] < 50, "Weak signal should have low composite score"
    
    print("✅ Composite score test passed")


if __name__ == "__main__":
    print("🧪 Running Quantitative Signal Calculator Tests\n")
    
    try:
        test_trend_score()
        test_momentum_score()
        test_volume_score()
        test_sentiment_score()
        test_composite_score()
        
        print("\n" + "="*50)
        print("✅ All tests passed!")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

