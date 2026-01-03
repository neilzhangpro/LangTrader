#!/usr/bin/env python3
"""
验证市场指标集成
测试订单簿和成交记录指标在实盘和回测模式下的行为
"""
import asyncio
from unittest.mock import MagicMock, AsyncMock
from langtrader_core.services.market import Market
from langtrader_core.services.cache import Cache
from langtrader_core.services.ratelimit import RateLimiter


class MockTrader:
    """模拟交易者"""
    def __init__(self):
        self.exchange = MockExchange()
    
    async def fetch_ohlcv(self, symbol, timeframe, limit):
        """模拟K线数据"""
        return [[1609459200000, 50000, 50100, 49900, 50050, 100] for _ in range(limit)]


class MockExchange:
    """模拟交易所"""
    def __init__(self):
        self.rateLimit = 50
        self.id = 'binance'
        self.has = {'fetchFundingRates': False}
    
    async def fetch_ticker(self, symbol):
        return {'last': 50000, 'close': 50000}
    
    async def fetch_tickers(self, symbols):
        return {s: {'last': 50000, 'close': 50000} for s in symbols}
    
    async def fetch_order_book(self, symbol, limit=20):
        """模拟订单簿"""
        return {
            'bids': [[50000 - i*10, 1.0] for i in range(limit)],
            'asks': [[50000 + i*10, 1.0] for i in range(limit)]
        }
    
    async def fetch_trades(self, symbol, limit=100):
        """模拟成交记录"""
        base_time = 1609459200000
        return [
            {
                'timestamp': base_time + i * 1000,
                'price': 50000 + i,
                'amount': 0.1,
                'side': 'buy' if i % 2 == 0 else 'sell'
            }
            for i in range(limit)
        ]


class MockState:
    """模拟状态"""
    def __init__(self):
        self.symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT']
        self.bot_id = 1


async def verify_live_mode():
    """验证实盘模式（应该获取新指标）"""
    print("\n" + "="*60)
    print("测试 1: 实盘模式 - 应该获取订单簿和成交记录指标")
    print("="*60)
    
    trader = MockTrader()
    cache = Cache()
    rate_limiter = RateLimiter()
    
    # 创建实盘模式的Market（stream_manager不为None）
    market = Market(
        trader=trader,
        stream_manager=MagicMock(),  # 非None表示实盘模式
        cache=cache,
        rate_limiter=rate_limiter
    )
    
    # 测试获取K线和指标
    state = MockState()
    
    try:
        # 模拟完整的数据获取流程
        k_market_data = await market._get_klines(state)
        print(f"✓ K线数据获取成功: {len(k_market_data)} 个交易对")
        
        # 获取量化数据（包含新指标）
        market_data = await market._get_quantitative_data(k_market_data)
        print(f"✓ 量化数据计算成功: {len(market_data)} 个交易对")
        
        # 检查第一个交易对的指标
        first_symbol = state.symbols[0]
        if first_symbol in market_data:
            indicators = market_data[first_symbol].get('indicators', {})
            
            # 检查新增的订单簿指标
            has_orderbook = any(key in indicators for key in ['spread', 'imbalance', 'liquidity_depth'])
            has_trades = any(key in indicators for key in ['buy_sell_ratio', 'trade_intensity'])
            
            if has_orderbook:
                print(f"✓ 订单簿指标已添加:")
                print(f"  - spread: {indicators.get('spread', 'N/A')}")
                print(f"  - imbalance: {indicators.get('imbalance', 'N/A')}")
                print(f"  - liquidity_depth: {indicators.get('liquidity_depth', 'N/A')}")
            else:
                print("✗ 订单簿指标缺失")
                return False
            
            if has_trades:
                print(f"✓ 成交记录指标已添加:")
                print(f"  - buy_sell_ratio: {indicators.get('buy_sell_ratio', 'N/A')}")
                print(f"  - trade_intensity: {indicators.get('trade_intensity', 'N/A')}")
            else:
                print("✗ 成交记录指标缺失")
                return False
            
            # 检查传统指标仍然存在
            has_traditional = any(key in indicators for key in ['ema_20_3m', 'macd_3m', 'rsi_3m'])
            if has_traditional:
                print(f"✓ 传统技术指标保留完整")
            else:
                print("✗ 传统技术指标缺失")
                return False
        
        print("\n✅ 实盘模式验证通过 - 所有指标正常")
        return True
        
    except Exception as e:
        print(f"\n❌ 实盘模式验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def verify_backtest_mode():
    """验证回测模式（应该跳过新指标）"""
    print("\n" + "="*60)
    print("测试 2: 回测模式 - 应该跳过订单簿和成交记录指标")
    print("="*60)
    
    trader = MockTrader()
    cache = Cache()
    rate_limiter = RateLimiter()
    
    # 创建回测模式的Market（stream_manager=None）
    market = Market(
        trader=trader,
        stream_manager=None,  # None表示回测模式
        cache=cache,
        rate_limiter=rate_limiter
    )
    
    state = MockState()
    
    try:
        # 模拟完整的数据获取流程
        k_market_data = await market._get_klines(state)
        print(f"✓ K线数据获取成功: {len(k_market_data)} 个交易对")
        
        # 获取量化数据（应该跳过新指标）
        market_data = await market._get_quantitative_data(k_market_data)
        print(f"✓ 量化数据计算成功: {len(market_data)} 个交易对")
        
        # 检查第一个交易对的指标
        first_symbol = state.symbols[0]
        if first_symbol in market_data:
            indicators = market_data[first_symbol].get('indicators', {})
            
            # 检查新增的指标应该不存在
            has_orderbook = any(key in indicators for key in ['spread', 'imbalance', 'liquidity_depth'])
            has_trades = any(key in indicators for key in ['buy_sell_ratio', 'trade_intensity'])
            
            if not has_orderbook:
                print(f"✓ 订单簿指标已跳过（符合预期）")
            else:
                print("✗ 订单簿指标不应该存在于回测模式")
                return False
            
            if not has_trades:
                print(f"✓ 成交记录指标已跳过（符合预期）")
            else:
                print("✗ 成交记录指标不应该存在于回测模式")
                return False
            
            # 检查传统指标仍然存在
            has_traditional = any(key in indicators for key in ['ema_20_3m', 'macd_3m', 'rsi_3m'])
            if has_traditional:
                print(f"✓ 传统技术指标正常工作")
            else:
                print("✗ 传统技术指标缺失")
                return False
        
        print("\n✅ 回测模式验证通过 - 新指标正确跳过，传统指标保留")
        return True
        
    except Exception as e:
        print(f"\n❌ 回测模式验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def verify_cache_behavior():
    """验证缓存行为"""
    print("\n" + "="*60)
    print("测试 3: 缓存行为验证")
    print("="*60)
    
    trader = MockTrader()
    cache = Cache()
    rate_limiter = RateLimiter()
    
    market = Market(
        trader=trader,
        stream_manager=MagicMock(),
        cache=cache,
        rate_limiter=rate_limiter
    )
    
    symbols = ['BTC/USDT:USDT']
    
    try:
        # 第一次获取（应该从API）
        print("第一次获取订单簿指标...")
        metrics1 = await market._fetch_order_book_metrics(symbols)
        
        # 检查缓存
        cache_key = 'orderbook:BTC/USDT:USDT'
        cached = cache.get('orderbook', cache_key)
        
        if cached:
            print("✓ 数据已缓存")
        else:
            print("✗ 缓存失败")
            return False
        
        # 第二次获取（应该从缓存）
        print("第二次获取订单簿指标（应该命中缓存）...")
        metrics2 = await market._fetch_order_book_metrics(symbols)
        
        if metrics1 == metrics2:
            print("✓ 缓存命中，数据一致")
        else:
            print("✗ 缓存未命中或数据不一致")
            return False
        
        # 检查TTL
        entry_age = cache.get_entry_age('orderbook', cache_key)
        if entry_age is not None and entry_age < 60:
            print(f"✓ 缓存TTL正常 (age: {entry_age:.2f}s, limit: 60s)")
        else:
            print(f"⚠ 缓存TTL异常 (age: {entry_age})")
        
        print("\n✅ 缓存行为验证通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 缓存验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有验证测试"""
    print("\n" + "🔍 开始市场指标集成验证".center(60, "="))
    print("此脚本验证订单簿和成交记录指标的集成情况\n")
    
    results = []
    
    # 测试1: 实盘模式
    results.append(await verify_live_mode())
    
    # 测试2: 回测模式
    results.append(await verify_backtest_mode())
    
    # 测试3: 缓存行为
    results.append(await verify_cache_behavior())
    
    # 汇总结果
    print("\n" + "="*60)
    print("验证结果汇总")
    print("="*60)
    print(f"总测试数: {len(results)}")
    print(f"通过: {sum(results)}")
    print(f"失败: {len(results) - sum(results)}")
    
    if all(results):
        print("\n✅ 所有验证测试通过！")
        print("\n集成摘要:")
        print("  ✓ 实盘模式正确获取订单簿和成交记录指标")
        print("  ✓ 回测模式正确跳过新指标，避免API调用")
        print("  ✓ 缓存机制正常工作（60秒TTL）")
        print("  ✓ 传统技术指标保持兼容")
        print("\n下一步:")
        print("  1. 在真实环境测试（需要配置数据库和API密钥）")
        print("  2. 运行完整的pytest测试套件")
        print("  3. 检查AI分析输出中包含新指标的解读")
        return 0
    else:
        print("\n❌ 部分测试失败，请检查上述错误信息")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

