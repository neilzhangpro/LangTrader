"""
测试 PnL 计算逻辑的正确性
"""


def test_long_position_profit():
    """测试多头盈利情况"""
    entry_price = 100.0
    exit_price = 110.0
    amount = 0.1  # 0.1 BTC
    
    # 成本 = 100 * 0.1 = 10 USD
    cost_basis = entry_price * amount
    # 价值 = 110 * 0.1 = 11 USD
    value_now = exit_price * amount
    # 盈亏 = 11 - 10 = 1 USD
    pnl_usd = value_now - cost_basis
    # 百分比 = 1 / 10 * 100 = 10%
    pnl_percent = (pnl_usd / cost_basis) * 100
    
    assert pnl_usd == 1.0
    assert pnl_percent == 10.0
    print(f"✅ Long profit: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)")


def test_long_position_loss():
    """测试多头亏损情况"""
    entry_price = 100.0
    exit_price = 90.0
    amount = 0.1  # 0.1 BTC
    
    cost_basis = entry_price * amount  # 10 USD
    value_now = exit_price * amount    # 9 USD
    pnl_usd = value_now - cost_basis   # -1 USD
    pnl_percent = (pnl_usd / cost_basis) * 100  # -10%
    
    assert pnl_usd == -1.0
    assert pnl_percent == -10.0
    print(f"✅ Long loss: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)")


def test_short_position_profit():
    """测试空头盈利情况"""
    entry_price = 100.0
    exit_price = 90.0
    amount = 0.1  # 0.1 BTC
    
    # 空头：入场时卖出获得 100 * 0.1 = 10 USD
    value_entry = entry_price * amount
    # 平仓时买回花费 90 * 0.1 = 9 USD
    cost_exit = exit_price * amount
    # 盈亏 = 10 - 9 = 1 USD
    pnl_usd = value_entry - cost_exit
    # 百分比 = (100 - 90) / 100 * 100 = 10%
    pnl_percent = ((entry_price - exit_price) / entry_price) * 100
    
    assert pnl_usd == 1.0
    assert pnl_percent == 10.0
    print(f"✅ Short profit: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)")


def test_short_position_loss():
    """测试空头亏损情况"""
    entry_price = 100.0
    exit_price = 110.0
    amount = 0.1  # 0.1 BTC
    
    value_entry = entry_price * amount  # 10 USD
    cost_exit = exit_price * amount     # 11 USD
    pnl_usd = value_entry - cost_exit   # -1 USD
    pnl_percent = ((entry_price - exit_price) / entry_price) * 100  # -10%
    
    assert pnl_usd == -1.0
    assert pnl_percent == -10.0
    print(f"✅ Short loss: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)")


def test_realistic_scenario_with_small_balance():
    """测试实际场景：小额余额交易"""
    # 假设账户余额 9.22 USDC
    balance = 9.22
    # BTC 价格 87,671 USDC
    btc_price = 87671.0
    # 使用 10% 仓位
    position_size_usd = balance * 0.1  # 0.922 USDC
    
    # 计算可买 BTC 数量
    amount_btc = position_size_usd / btc_price  # 约 0.0000105 BTC
    
    # 假设价格上涨 1%
    entry_price = btc_price
    exit_price = btc_price * 1.01
    
    # 计算盈亏
    cost_basis = entry_price * amount_btc
    value_now = exit_price * amount_btc
    pnl_usd = value_now - cost_basis
    pnl_percent = (pnl_usd / cost_basis) * 100
    
    # 验证
    assert abs(cost_basis - position_size_usd) < 0.0001  # 成本应该等于仓位大小
    assert abs(pnl_percent - 1.0) < 0.01  # 1% 价格变化应该产生 1% 收益
    assert pnl_usd > 0  # 应该盈利
    assert pnl_usd < 0.02  # 盈利应该是小额（约 0.00922 USDC）
    
    print(f"✅ Realistic scenario:")
    print(f"   Balance: ${balance:.2f}")
    print(f"   Position: ${position_size_usd:.4f} ({position_size_usd/balance*100:.1f}%)")
    print(f"   Amount: {amount_btc:.8f} BTC")
    print(f"   Entry: ${entry_price:.2f}")
    print(f"   Exit: ${exit_price:.2f}")
    print(f"   PnL: ${pnl_usd:.4f} ({pnl_percent:+.2f}%)")


def test_wrong_calculation_example():
    """演示错误的计算方式（使用大额 amount）"""
    # 这是之前数据库中的错误数据
    entry_price = 87671.53
    exit_price = 87802.44
    wrong_amount = 4500.0  # 错误：使用了固定的大额数量
    
    # 错误的计算（之前的方式）
    wrong_pnl = (exit_price - entry_price) * wrong_amount
    
    # 正确的计算（假设实际余额 9.22 USDC，10% 仓位）
    balance = 9.22
    position_size = balance * 0.1
    correct_amount = position_size / entry_price
    correct_pnl = (exit_price - entry_price) * correct_amount
    
    print(f"❌ Wrong calculation:")
    print(f"   Amount: {wrong_amount} (unrealistic)")
    print(f"   PnL: ${wrong_pnl:,.2f} (absurd!)")
    print(f"")
    print(f"✅ Correct calculation:")
    print(f"   Balance: ${balance:.2f}")
    print(f"   Position: ${position_size:.4f}")
    print(f"   Amount: {correct_amount:.8f} BTC")
    print(f"   PnL: ${correct_pnl:.4f} (reasonable)")
    
    # 验证差异巨大
    assert abs(wrong_pnl) > 100000  # 错误计算产生荒谬的数字
    assert abs(correct_pnl) < 1  # 正确计算产生合理的数字


if __name__ == "__main__":
    print("=" * 60)
    print("Testing PnL Calculation Logic")
    print("=" * 60)
    print()
    
    test_long_position_profit()
    test_long_position_loss()
    test_short_position_profit()
    test_short_position_loss()
    print()
    test_realistic_scenario_with_small_balance()
    print()
    test_wrong_calculation_example()
    
    print()
    print("=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

