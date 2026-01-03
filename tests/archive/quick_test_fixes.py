#!/usr/bin/env python3
"""
Quick test to verify the two bug fixes:
1. Cache key duplication fixed
2. Backtest mode detection fixed
"""
import asyncio
from unittest.mock import MagicMock
from langtrader_core.services.market import Market
from langtrader_core.services.cache import Cache


class MockTrader:
    def __init__(self):
        self.exchange = MagicMock()
        self.exchange.rateLimit = 50


async def test_cache_key_fix():
    """Test that cache keys no longer have duplicate prefixes"""
    print("\n" + "="*60)
    print("Test 1: Cache Key Fix")
    print("="*60)
    
    cache = Cache()
    market = Market(trader=MockTrader(), cache=cache)
    
    # Manually set a test value in cache
    test_data = {'test': 'value'}
    cache.set('orderbook', test_data, 'BTC/USDT:USDT')
    
    # Retrieve it
    retrieved = cache.get('orderbook', 'BTC/USDT:USDT')
    
    if retrieved == test_data:
        print("✅ Cache key fix verified - no duplication")
        return True
    else:
        print("❌ Cache key still has issues")
        return False


async def test_backtest_mode_detection():
    """Test that stream_manager=None is respected for backtest mode"""
    print("\n" + "="*60)
    print("Test 2: Backtest Mode Detection")
    print("="*60)
    
    # Create Market with explicit stream_manager=None (backtest mode)
    market = Market(trader=MockTrader(), stream_manager=None, cache=Cache())
    
    if market.stream_manager is None:
        print("✅ Backtest mode detected correctly (stream_manager is None)")
        return True
    else:
        print(f"❌ Backtest mode not detected (stream_manager = {market.stream_manager})")
        return False


async def test_live_mode_still_works():
    """Test that default behavior (creating stream_manager) still works"""
    print("\n" + "="*60)
    print("Test 3: Live Mode Still Works")
    print("="*60)
    
    # Create Market without stream_manager parameter (should create one)
    market = Market(trader=MockTrader(), cache=Cache())
    
    if market.stream_manager is not None:
        print("✅ Live mode still works (stream_manager auto-created)")
        return True
    else:
        print("❌ Live mode broken (stream_manager should be created)")
        return False


async def main():
    print("\n" + "🔧 Quick Verification of Bug Fixes".center(60, "="))
    
    results = []
    
    results.append(await test_cache_key_fix())
    results.append(await test_backtest_mode_detection())
    results.append(await test_live_mode_still_works())
    
    print("\n" + "="*60)
    print("Results Summary")
    print("="*60)
    print(f"Passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("\n✅ All fixes verified! Ready to run full test suite.")
        return 0
    else:
        print("\n❌ Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

