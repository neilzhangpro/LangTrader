# tests/test_fee_calculator.py
"""
测试手续费计算器
"""
import pytest
from langtrader_core.services.fee_calculator import FeeCalculator


class MockExchange:
    """模拟交易所（用于测试）"""
    def __init__(self, markets=None, fees=None):
        self.markets = markets or {}
        self.fees = fees or {}


def test_get_fee_rate_from_markets():
    """测试从markets获取费率"""
    exchange = MockExchange(markets={
        'BTC/USDC:USDC': {
            'maker': 0.0002,
            'taker': 0.0005
        }
    })
    
    # 测试市价单（taker）
    rate = FeeCalculator.get_trading_fee_rate(exchange, 'BTC/USDC:USDC', 'market')
    assert rate == 0.0005
    
    # 测试限价单（maker）
    rate = FeeCalculator.get_trading_fee_rate(exchange, 'BTC/USDC:USDC', 'limit')
    assert rate == 0.0002


def test_get_fee_rate_from_exchange_fees():
    """测试从exchange.fees获取费率"""
    exchange = MockExchange(fees={
        'trading': {
            'maker': 0.0001,
            'taker': 0.0004
        }
    })
    
    rate = FeeCalculator.get_trading_fee_rate(exchange, 'BTC/USDC:USDC', 'market')
    assert rate == 0.0004


def test_get_fee_rate_fallback():
    """测试fallback默认费率"""
    exchange = MockExchange()
    
    rate = FeeCalculator.get_trading_fee_rate(exchange, 'BTC/USDC:USDC', 'market')
    assert rate == 0.001  # 默认值


def test_calculate_fee():
    """测试手续费计算"""
    # 测试：$10,000名义价值，0.05%费率
    fee = FeeCalculator.calculate_fee(10000, 0.0005)
    assert fee == 5.0
    
    # 测试：$4,500名义价值，0.05%费率
    fee = FeeCalculator.calculate_fee(4500, 0.0005)
    assert fee == 2.25


def test_convert_usd_to_coin():
    """测试USD转币数量"""
    # $4,500 @ $87,671.53 = 0.0513 BTC
    coins = FeeCalculator.convert_usd_to_coin_amount(4500, 87671.53)
    assert abs(coins - 0.0513) < 0.0001
    
    # $10,000 @ $3,000 = 3.333 ETH
    coins = FeeCalculator.convert_usd_to_coin_amount(10000, 3000)
    assert abs(coins - 3.333) < 0.001


def test_exchange_specific_rates():
    """测试交易所特定费率"""
    # Hyperliquid
    rates = FeeCalculator.get_exchange_specific_rates('hyperliquid')
    assert rates['maker'] == 0.0
    assert rates['taker'] == 0.00035
    
    # Binance
    rates = FeeCalculator.get_exchange_specific_rates('binance')
    assert rates['maker'] == 0.0002
    assert rates['taker'] == 0.0004
    
    # 未知交易所
    rates = FeeCalculator.get_exchange_specific_rates('unknown')
    assert rates['maker'] == 0.0005
    assert rates['taker'] == 0.001


def test_real_world_scenario():
    """测试真实场景：BTC开仓$4,500"""
    # 场景：BTC价格$87,671.53，开仓$4,500
    price = 87671.53
    usd_amount = 4500
    fee_rate = 0.0005  # 0.05%
    
    # 1. 转换为币数量
    coin_amount = FeeCalculator.convert_usd_to_coin_amount(usd_amount, price)
    assert abs(coin_amount - 0.0513) < 0.0001
    
    # 2. 计算名义价值（应该≈usd_amount）
    notional = coin_amount * price
    assert abs(notional - usd_amount) < 1  # 允许1美元误差
    
    # 3. 计算手续费
    fee = FeeCalculator.calculate_fee(notional, fee_rate)
    assert abs(fee - 2.25) < 0.01  # $2.25手续费
    
    # 验证：不是错误的$197,260
    assert fee < 10  # 手续费应该远小于10美元


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

