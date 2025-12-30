# packages/langtrader_core/services/market.py
"""
市场数据服务 - 负责获取数据并计算指标
组合使用 IndicatorCalculator（而非继承）
"""
from langtrader_core.services.indicators import IndicatorCalculator, Kline, ohlcv_to_klines
from langtrader_core.services.trader import Trader
from langtrader_core.services.cache import Cache
from langtrader_core.services.ratelimit import RateLimiter
from langtrader_core.services.stream_manager import DynamicStreamManager
from langtrader_core.graph.state import State
from langtrader_core.utils import get_logger
from typing import Optional, List, Dict
import time

logger = get_logger("market")


class Market:
    """
    市场数据服务
    - 负责获取 K 线数据
    - 使用 IndicatorCalculator 计算指标
    - 通过依赖注入获取 Cache 和 RateLimiter
    """
    
    def __init__(
        self,
        trader: Optional[Trader] = None,
        stream_manager: Optional[DynamicStreamManager] = None,
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
        
        # Stream Manager
        if stream_manager:
            self.stream_manager = stream_manager
        elif trader:
            self.stream_manager = DynamicStreamManager(trader)
        else:
            self.stream_manager = None
        
        # 指标计算器（纯静态方法类）
        self.calc = IndicatorCalculator
    
    async def _get_realtime_price(self, symbol: str) -> float:
        """
        从 ticker API 获取实时价格（解决 testnet 低流动性币种 K 线数据过旧问题）
        """
        try:
            ticker = await self.trader.exchange.fetch_ticker(symbol)
            price = ticker.get('last') or ticker.get('close') or 0
            if price:
                logger.debug(f"📈 {symbol} realtime price: {price}")
            return float(price)
        except Exception as e:
            logger.warning(f"Failed to fetch ticker for {symbol}: {e}")
            return 0
    
    async def _get_realtime_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        批量获取实时价格
        """
        prices = {}
        try:
            # 尝试批量获取（更高效）
            tickers = await self.trader.exchange.fetch_tickers(symbols)
            for symbol in symbols:
                if symbol in tickers:
                    ticker = tickers[symbol]
                    prices[symbol] = float(ticker.get('last') or ticker.get('close') or 0)
            logger.info(f"📈 Fetched {len(prices)} realtime prices via batch API")
        except Exception as e:
            logger.warning(f"Batch ticker fetch failed, falling back to individual: {e}")
            # 回退到逐个获取
            for symbol in symbols:
                prices[symbol] = await self._get_realtime_price(symbol)
        return prices
    
    async def _fetch_funding_rates(self, symbols: List[str]) -> Dict[str, float]:
        """
        批量获取资金费率
        参考: https://docs.ccxt.com/README?id=funding-rate
        """
        funding_rates = {}
        
        try:
            # CCXT Pro 支持的交易所可以批量获取
            if self.trader.exchange.has.get('fetchFundingRates'):
                logger.info(f"💰 Fetching funding rates for {len(symbols)} symbols...")
                
                # 批量获取
                rates = await self.trader.exchange.fetchFundingRates(symbols)
                
                for symbol in symbols:
                    if symbol in rates:
                        rate_data = rates[symbol]
                        # 获取当前资金费率
                        funding_rate = rate_data.get('fundingRate', 0)
                        funding_rates[symbol] = float(funding_rate) if funding_rate else 0
                        
                        logger.debug(
                            f"  {symbol}: funding_rate={funding_rate*100:.4f}%"
                        )
                
                logger.info(f"✅ Fetched funding rates for {len(funding_rates)} symbols")
            else:
                logger.warning(
                    f"Exchange {self.trader.exchange.id} does not support fetchFundingRates"
                )
                # 为所有币种返回 0（表示无数据）
                funding_rates = {symbol: 0 for symbol in symbols}
        
        except Exception as e:
            logger.error(f"Failed to fetch funding rates: {e}")
            funding_rates = {symbol: 0 for symbol in symbols}
        
        return funding_rates
    
    async def _get_klines(self, state: State):
        """
        Get klines from cache or trader
        
        ✅ 修复：同时检查缓存条目年龄和 K 线时间戳，避免对低流动性币种无限请求 REST API
        ✅ 回测模式：跳过缓存过期检查（stream_manager=None 表示回测模式）
        """
        market_data = {}
        now_ms = int(time.time() * 1000)
        
        # 🔧 回测模式检测：stream_manager=None 表示回测模式
        is_backtest = self.stream_manager is None
        
        for symbol in state.symbols:
            symbol_data = {}
            cache_key_3m = f'{symbol}:3m:100'
            cache_key_4h = f'{symbol}:4h:100'
            
            # ========== 1. 获取 3m 数据 ==========
            ohlcv_3m = None
            need_refresh_3m = False
            
            if self.stream_manager:
                ohlcv_3m = await self.stream_manager.get_latest_ohlcv(symbol, '3m')
            elif self.cache:
                ohlcv_3m = self.cache.get('ohlcv_3m', cache_key_3m)
            
            # 🔧 回测模式：跳过缓存过期检查，直接信任预加载的数据
            if is_backtest:
                need_refresh_3m = ohlcv_3m is None or len(ohlcv_3m) == 0
            elif ohlcv_3m and len(ohlcv_3m) > 0 and self.cache:
                # 实盘模式：检查缓存条目年龄
                cache_age = self.cache.get_entry_age('ohlcv_3m', cache_key_3m)
                last_candle_ts = ohlcv_3m[-1][0]
                data_age_min = (now_ms - last_candle_ts) / 1000 / 60
                
                if cache_age is not None:
                    # 只有当缓存条目本身超过 3 分钟（一个交易 cycle）才认为需要刷新
                    if cache_age > 3 * 60:
                        logger.warning(f"⚠️  {symbol} 3m cache stale "
                                     f"(cache: {cache_age/60:.1f} min, data: {data_age_min:.1f} min)")
                        need_refresh_3m = True
                    elif data_age_min > 60:
                        # 数据很旧但缓存刚更新，只记录不刷新（避免低流动性币种无限请求）
                        logger.debug(f"📊 {symbol} 3m data old ({data_age_min:.0f} min) "
                                   f"but cache fresh ({cache_age:.0f}s)")
                else:
                    need_refresh_3m = True
            else:
                need_refresh_3m = True
            
            if not need_refresh_3m and ohlcv_3m:
                symbol_data['3m'] = ohlcv_3m
            else:
                # 缓存失效或过期，强制从 REST API 获取
                try:
                    if self.rate_limiter:
                        await self.rate_limiter.wait_if_needed()
                    ohlcv_3m = await self.trader.fetch_ohlcv(symbol, '3m', limit=100)
                    if ohlcv_3m:
                        symbol_data['3m'] = ohlcv_3m
                        if self.cache:
                            self.cache.set('ohlcv_3m', ohlcv_3m, cache_key_3m)
                except Exception as e:
                    logger.error(f"Failed to fetch 3m data for {symbol}: {e}")
            
            # ========== 2. 获取 4h 数据 ==========
            ohlcv_4h = self.cache.get('ohlcv_4h', cache_key_4h) if self.cache else None
            need_refresh_4h = False
            
            # 🔧 回测模式：跳过缓存过期检查
            if is_backtest:
                need_refresh_4h = ohlcv_4h is None or len(ohlcv_4h) == 0
            elif ohlcv_4h and len(ohlcv_4h) > 0 and self.cache:
                # 实盘模式：检查 4h 缓存条目年龄
                cache_age = self.cache.get_entry_age('ohlcv_4h', cache_key_4h)
                last_candle_ts = ohlcv_4h[-1][0]
                data_age_hours = (now_ms - last_candle_ts) / 1000 / 3600
                
                if cache_age is not None:
                    # 只有当缓存条目本身超过 4 小时才认为需要刷新
                    if cache_age > 4 * 3600:
                        logger.warning(f"⚠️  {symbol} 4h cache stale "
                                     f"(cache: {cache_age/3600:.1f} h, data: {data_age_hours:.1f} h)")
                        need_refresh_4h = True
                else:
                    need_refresh_4h = True
            else:
                need_refresh_4h = True
            
            if not need_refresh_4h and ohlcv_4h:
                symbol_data['4h'] = ohlcv_4h
            else:
                # 从 REST API 获取
                try:
                    if self.rate_limiter:
                        await self.rate_limiter.wait_if_needed()
                    ohlcv_4h = await self.trader.fetch_ohlcv(symbol, '4h', limit=100)
                    if ohlcv_4h:
                        symbol_data['4h'] = ohlcv_4h
                        if self.cache:
                            self.cache.set('ohlcv_4h', ohlcv_4h, cache_key_4h)
                except Exception as e:
                    logger.error(f"Failed to fetch 4h data for {symbol}: {e}")
            
            # 只有至少有一个时间框架的数据才加入
            if symbol_data:
                market_data[symbol] = symbol_data
        return market_data

    async def _get_quantitative_data(self, k_market_data: Dict):
        """
        Get quantitative data from klines
        ✅ 修复：使用 ticker API 获取实时价格，解决 testnet 低流动性币种价格不更新问题
        ✅ 新增：获取资金费率数据供 AI 决策使用
        """
        logger.info(f"Getting quantitative data from klines: {len(k_market_data)}")
        
        # ✅ 先批量获取所有币种的实时价格
        symbols = list(k_market_data.keys())
        realtime_prices = await self._get_realtime_prices(symbols)
        
        # ✅ 批量获取资金费率（新增）
        funding_rates = await self._fetch_funding_rates(symbols)

        for symbol, data in k_market_data.items():
            indicators = {}

            try:
                # 3m indicators
                if '3m' in data and data['3m']:
                    # 使用统一的转换函数
                    klines_3m = ohlcv_to_klines(data['3m'])
                    
                    # 使用静态方法计算指标
                    indicators['ema_20_3m'] = self.calc.calculate_ema(klines_3m, 20)
                    indicators['macd_3m'] = self.calc.calculate_macd(klines_3m)
                    indicators['rsi_3m'] = self.calc.calculate_rsi(klines_3m, 7)
                    indicators['atr_3m'] = self.calc.calculate_atr(klines_3m, 14)
                    
                    # ✅ 使用实时 ticker 价格替代 K 线最后收盘价
                    kline_price = klines_3m[-1].close if klines_3m else 0
                    realtime_price = realtime_prices.get(symbol, 0)
                    indicators['current_price'] = realtime_price if realtime_price > 0 else kline_price
                    indicators['kline_price'] = kline_price  # 保留 K 线价格用于对比

                    # Advanced indicators
                    indicators['bollinger_3m'] = self.calc.calculate_bollinger_bands(klines_3m, 20, 2.0)
                    indicators['vwap_3m'] = self.calc.calculate_vwap(klines_3m)
                    indicators['volume_ratio_3m'] = self.calc.calculate_volume_ratio(klines_3m, 20)
                    indicators['atr_percent_3m'] = self.calc.calculate_atr_percent(klines_3m, 14)
                    indicators['stochastic_3m'] = self.calc.calculate_stochastic(klines_3m, 14, 3)
                    indicators['obv_3m'] = self.calc.calculate_obv(klines_3m)
                
                if '4h' in data and data['4h']:
                    # 使用统一的转换函数
                    klines_4h = ohlcv_to_klines(data['4h'])
                    
                    # Basic indicators
                    indicators['ema_20_4h'] = self.calc.calculate_ema(klines_4h, 20)
                    indicators['ema_50_4h'] = self.calc.calculate_ema(klines_4h, 50)
                    indicators['ema_200_4h'] = self.calc.calculate_ema(klines_4h, 200)
                    indicators['macd_4h'] = self.calc.calculate_macd(klines_4h)
                    indicators['rsi_4h'] = self.calc.calculate_rsi(klines_4h, 7)
                    indicators['atr_4h'] = self.calc.calculate_atr(klines_4h, 14)

                    # Advanced indicators
                    indicators['adx_4h'] = self.calc.calculate_adx(klines_4h, 14)
                    indicators['bollinger_4h'] = self.calc.calculate_bollinger_bands(klines_4h, 20, 2.0)
                    indicators['atr_percent_4h'] = self.calc.calculate_atr_percent(klines_4h, 14)
                    indicators['stochastic_4h'] = self.calc.calculate_stochastic(klines_4h, 14, 3)
                    indicators['obv_4h'] = self.calc.calculate_obv(klines_4h)
                
                # 添加资金费率到指标
                indicators['funding_rate'] = funding_rates.get(symbol, 0)
                
                data['indicators'] = indicators
            
            except Exception as e:
                logger.error(f"Failed to get quantitative data for {symbol}: {e}")
                data['indicators'] = {}

        return k_market_data

    async def run(self, state: State):
        """
        获取市场数据并计算指标
        """
        k_market_data = await self._get_klines(state)
        market_data = await self._get_quantitative_data(k_market_data)

        
        # 统计信息
        count_3m = sum(1 for v in market_data.values() if v.get('3m'))
        count_4h = sum(1 for v in market_data.values() if v.get('4h'))
        
        logger.info(f"✅ Market data ready: {len(market_data)}/{len(state.symbols)} symbols")
        logger.info(f"   3m data: {count_3m}/{len(state.symbols)}")
        logger.info(f"   4h data: {count_4h}/{len(state.symbols)}")

        return market_data
