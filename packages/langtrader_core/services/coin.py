# packages/langtrader_core/services/coin.py
"""
选币服务
- select top -> list of coins
- select io top -> list of coins
- combine the two lists -> list of coins
- then score the coins and return the top 20 coins
"""

from langtrader_core.utils import get_logger
from langtrader_core.services.trader import Trader
from langtrader_core.services.cache import Cache
from langtrader_core.services.ratelimit import RateLimiter
from langtrader_core.services.indicators import IndicatorCalculator, ohlcv_to_klines
from typing import Optional, List, Dict
import asyncio

logger = get_logger("coin")


class Coin:
    """
    选币服务 (async version)
    通过依赖注入获取 Cache 和 RateLimiter
    """
    
    def __init__(
        self, 
        trader: Optional[Trader] = None,
        cache: Optional[Cache] = None,
        rate_limiter: Optional[RateLimiter] = None
    ):
        self.trader = trader
        # 通过注入获取，否则创建默认实例（向后兼容）
        self.cache = cache if cache is not None else Cache()
        self.rate_limiter = rate_limiter if rate_limiter is not None else RateLimiter()
        
        # 设置限流器速率
        if self.rate_limiter and trader and trader.exchange:
            self.rate_limiter.set_rate_limit(trader.exchange.rateLimit)
        
        # 指标计算器（纯静态方法类）
        self.calc = IndicatorCalculator

    def _static_filter(self, limit=20, quote_whitelist=("USDT", "USDC")) -> List[str]:
        """静态过滤币种"""
        markets = self.trader.markets
        symbols = []
        for sym, m in markets.items():
            if not (m.get("swap") and m.get("active")):
                continue
            if m.get("quote") not in quote_whitelist:
                continue
            limits = m.get("limits", {})
            min_cost = (limits.get("cost") or {}).get("min")
            if min_cost and min_cost > 50:   # 过滤门槛过高的合约
                continue
            symbols.append(sym)
        return symbols[:limit]

    async def _fetch_tickers(self, symbols: List[str]) -> Dict[str, dict]:
        """
        Fetch tickers using WebSocket (async)
        """
        symbols_key = '_'.join(sorted(symbols))
        cached = self.cache.get('tickers', symbols_key)
        if cached:
            logger.debug(f"Tickers cached: {len(cached)} items")
            return cached

        # Use watch_tickers from CCXT Pro
        tickers = await self.trader.watch_tickers(symbols)
        self.cache.set('tickers', tickers, symbols_key)
        return tickers

    async def _fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100):
        """
        获取 OHLCV 数据（带缓存和限流）
        """
        cache_type = f'ohlcv_{timeframe}' if timeframe in ['3m', '4h'] else 'ohlcv'
        key = f'{symbol}:{timeframe}:{limit}'
        
        cached = self.cache.get(cache_type, key)
        if cached:
            logger.debug(f"OHLCV cached for {symbol} {timeframe}")
            return cached
        
        logger.info(f"OHLCV cache MISS for {symbol} {timeframe}, fetching...")
        if self.rate_limiter:
            await self.rate_limiter.wait_if_needed()
        
        ohlcv = await self.trader.fetch_ohlcv(symbol, timeframe, limit)
        self.cache.set(cache_type, ohlcv, key)
        return ohlcv

    async def select_io_top(self, limit=20) -> List[str]:
        """
        Select coins by open interest data (async)
        """
        cached = self.cache.get('open_interests')
        if cached:
            logger.debug(f"Open interests cached: {len(cached)} items")
            return cached
        
        # 添加调试日志查看交易所能力
        logger.info(f"Checking fetchOpenInterests support...")
        
        # 🔧 修复：添加 None 检查，避免回测时 MockTrader.exchange 为 None 导致的错误
        if self.trader.exchange and hasattr(self.trader.exchange, 'has'):
            logger.info(f"Exchange has fetchOpenInterests: {self.trader.exchange.has.get('fetchOpenInterests', False)}")
            
            if self.trader.exchange.has.get('fetchOpenInterests'):
                logger.info("Fetching open interests via REST API...")
                # 在 CCXT Pro 中所有方法都是异步的，必须使用 await
                open_interests = await self.trader.exchange.fetchOpenInterests()
                
                logger.info(f"Received {len(open_interests)} open interest records")
                
                filtered = {k: v for k, v in open_interests.items() 
                        if v.get('openInterestAmount') is not None}
                
                logger.info(f"After filtering: {len(filtered)} valid records")
                
                top_openio = sorted(filtered.items(), 
                                key=lambda x: x[1]['openInterestAmount'], 
                                reverse=True)
                result = [x[0] for x in top_openio[:limit]]
                self.cache.set('open_interests', result)
                logger.info(f"Top {limit} by open interest: {result}")
                return result
            else:
                logger.warning(f"Exchange does not support fetchOpenInterests")
        else:
            logger.debug("Exchange does not support fetchOpenInterests or exchange is None")
        
        return []
    
    def select_top(self, limit=20) -> List[str]:
        """
        Select the top coins (sync - no API call needed)
        """
        return self._static_filter(limit=limit)

    async def _top_20_coins(self, symbols: List[str], limit=20) -> List[str]:
        """
        Return a coins list with the top 20 coins by volume and spread (async)
        """
        tickers = await self._fetch_tickers(symbols)
        ranked = []
        for sym in symbols:
            t = tickers.get(sym)
            if not t:
                continue
            bid, ask = t.get("bid"), t.get("ask")
            if not bid or not ask:
                continue
            spread = (ask - bid) / ask if ask else 1
            qvol = t.get("quoteVolume") or 0
            change = abs(t.get("percentage") or 0)
            if spread > 0.005:   # 0.5%
                continue
            if change > 30:      # 避免极端波动
                continue
            ranked.append((sym, qvol, spread, t.get("info", {})))
        ranked.sort(key=lambda x: (-x[1], x[2]))
        return [r[0] for r in ranked[:limit]]

    def combine_unique_coins(self, io_top_coins: List[str], top_coins: List[str], limit: int = 5) -> List[str]:
        """
        合并去重 io top coins 和 top coins
        
        Args:
            io_top_coins: 按 Open Interest 排序的币种
            top_coins: 按成交量排序的币种
            limit: 返回数量限制
            
        Returns:
            去重后的币种列表
        """
        return list(dict.fromkeys(io_top_coins + top_coins))[:limit]
    
    # 保留旧方法名作为别名（向后兼容）
    def combin_uni_coins(self, io_top_coins: List[str], top_coins: List[str], limit: int = 5) -> List[str]:
        """
        [Deprecated] 使用 combine_unique_coins 替代
        """
        return self.combine_unique_coins(io_top_coins, top_coins, limit)

    async def score_coins(self, coins: List[str]) -> List[str]:
        """
        对币种列表评分并排序
        
        Args:
            coins: 待评分的币种列表
            
        Returns:
            按分数排序的币种列表（高分在前）
        """
        logger.info(f"Starting to score {len(coins)} coins with concurrent processing...")
        
        # Control concurrency to avoid overwhelming the API
        semaphore = asyncio.Semaphore(5)
        
        async def process_one_coin(coin: str, idx: int):
            """Process a single coin: fetch data and calculate score"""
            async with semaphore:
                logger.info(f"Processing coin {idx}/{len(coins)}: {coin}")
                
                try:
                    # Concurrently fetch both timeframes
                    klines_3m_raw, klines_4h_raw = await asyncio.gather(
                        self._fetch_ohlcv(coin, timeframe='3m', limit=100),
                        self._fetch_ohlcv(coin, timeframe='4h', limit=100),
                        return_exceptions=True
                    )
                    
                    # Check for exceptions
                    if isinstance(klines_3m_raw, Exception):
                        logger.error(f"✗ Failed to fetch 3m data for {coin}: {klines_3m_raw}")
                        return None
                    if isinstance(klines_4h_raw, Exception):
                        logger.error(f"✗ Failed to fetch 4h data for {coin}: {klines_4h_raw}")
                        return None
                    
                    logger.debug(f"Got {len(klines_3m_raw)} 3m and {len(klines_4h_raw)} 4h candles")
                    
                    # Verify data
                    if not klines_3m_raw or len(klines_3m_raw) < 20:
                        logger.warning(f"Skipping {coin}: insufficient 3m data")
                        return None
                    
                    if not klines_4h_raw or len(klines_4h_raw) < 20:
                        logger.warning(f"Skipping {coin}: insufficient 4h data")
                        return None
                    
                    # 使用统一的转换函数
                    klines_3m = ohlcv_to_klines(klines_3m_raw)
                    klines_4h = ohlcv_to_klines(klines_4h_raw)
                    
                    # Using 3m Klines to get the current price
                    current_price = klines_3m[-1].close
                    
                    logger.debug(f"Calculating indicators for {coin}...")
                    
                    # Calculate indicators using static methods
                    ema_3m = self.calc.calculate_ema(klines_3m, 20)
                    macd_3m = self.calc.calculate_macd(klines_3m)
                    rsi_3m = self.calc.calculate_rsi(klines_3m)
                    
                    ema_4h = self.calc.calculate_ema(klines_4h, 20)
                    macd_4h = self.calc.calculate_macd(klines_4h)
                    rsi_4h = self.calc.calculate_rsi(klines_4h)
                    
                    # Calculate score using static method
                    score = self.calc.score_coins(indicators={
                        'current_price': current_price,
                        'ema_3m': ema_3m, 'macd_3m': macd_3m, 'rsi_3m': rsi_3m,
                        'ema_4h': ema_4h, 'macd_4h': macd_4h, 'rsi_4h': rsi_4h,
                    })
                    
                    logger.info(f"✓ {coin} scored: {score}")
                    return (coin, score)
                    
                except Exception as e:
                    logger.error(f"✗ Failed to process {coin}: {e}")
                    return None
        
        # Process all coins concurrently
        tasks = [process_one_coin(coin, idx) for idx, coin in enumerate(coins, 1)]
        results = await asyncio.gather(*tasks)
        
        # Filter out failed results and build final dictionary
        scored_coins = {coin: score for result in results if result for coin, score in [result]}
        
        logger.info(f"Completed scoring. Total: {len(scored_coins)}/{len(coins)} coins successfully scored")
        
        # Rank the final coins
        ranked = sorted(scored_coins.items(), key=lambda x: x[1], reverse=True)
        logger.info(f"Top 10 scored coins: {[c for c, _ in ranked[:10]]}")
        
        return [coin for coin, _ in ranked]
