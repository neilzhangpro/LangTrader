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
from langtrader_core.services.config_manager import BotConfig
from langtrader_core.graph.state import State
from langtrader_core.utils import get_logger
from typing import Optional, List, Dict
import time

logger = get_logger("market")

# Sentinel value to distinguish "not provided" from "explicitly None"
_UNSET = object()


class Market:
    """
    市场数据服务
    - 负责获取 K 线数据
    - 使用 IndicatorCalculator 计算指标
    - 通过依赖注入获取 Cache 和 RateLimiter
    - 使用 BotConfig 获取动态配置
    """
    
    def __init__(
        self,
        trader: Optional[Trader] = None,
        stream_manager: Optional[DynamicStreamManager] = _UNSET,
        cache: Optional[Cache] = None,
        rate_limiter: Optional[RateLimiter] = None,
        bot_config: Optional[BotConfig] = None
    ):
        self.trader = trader
        self.bot_config = bot_config
        
        # 通过注入获取，否则创建默认实例（向后兼容）
        self.cache = cache if cache is not None else Cache()
        self.rate_limiter = rate_limiter if rate_limiter is not None else RateLimiter()
        
        # 设置限流器速率
        if self.rate_limiter and trader and trader.exchange:
            self.rate_limiter.set_rate_limit(trader.exchange.rateLimit)
        
        # Stream Manager
        # 使用sentinel值区分"未提供"和"显式传入None"（回测模式）
        if stream_manager is not _UNSET:
            # 显式传入值（包括None）
            self.stream_manager = stream_manager
        elif trader:
            # 未传入stream_manager，但有trader，创建默认的
            self.stream_manager = DynamicStreamManager(trader)
        else:
            # 既没有stream_manager也没有trader
            self.stream_manager = None
        
        # 指标计算器（纯静态方法类）
        self.calc = IndicatorCalculator
        
        # 日志配置信息
        if self.bot_config:
            logger.info(f"Market service initialized with dynamic config:")
            logger.info(f"  Timeframes: {self.bot_config.timeframes}")
            logger.info(f"  OHLCV limits: {[self.bot_config.get_ohlcv_limit(tf) for tf in self.bot_config.timeframes]}")
    
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
        批量获取实时价格（优先使用缓存）
        
        优化：coins_pick 阶段可能已通过 watch_tickers 缓存了 tickers 数据，
        此处优先复用，避免重复请求。
        """
        prices = {}
        
        # 1. 优先从缓存获取（coins_pick 使用相同的 symbols_key）
        if self.cache:
            symbols_key = '_'.join(sorted(symbols))
            cached_tickers = self.cache.get('tickers', symbols_key)
            if cached_tickers:
                for symbol in symbols:
                    if symbol in cached_tickers:
                        ticker = cached_tickers[symbol]
                        price = float(ticker.get('last') or ticker.get('close') or 0)
                        if price > 0:
                            prices[symbol] = price
                if len(prices) == len(symbols):
                    logger.debug(f"📦 Using {len(prices)} cached ticker prices")
                    return prices
                # 部分命中，记录缺失的
                logger.debug(f"📦 Partial cache hit: {len(prices)}/{len(symbols)} prices")
        
        # 2. 缓存未完全命中，回退到 API 获取
        missing_symbols = [s for s in symbols if s not in prices]
        if missing_symbols:
            try:
                tickers = await self.trader.exchange.fetch_tickers(missing_symbols)
                for symbol in missing_symbols:
                    if symbol in tickers:
                        ticker = tickers[symbol]
                        prices[symbol] = float(ticker.get('last') or ticker.get('close') or 0)
                logger.info(f"📈 Fetched {len(missing_symbols)} realtime prices via API")
            except Exception as e:
                logger.warning(f"Batch ticker fetch failed, falling back to individual: {e}")
                for symbol in missing_symbols:
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
    
    async def _fetch_order_book_metrics(self, symbols: List[str]) -> Dict[str, dict]:
        """
        批量获取订单簿深度指标
        
        Returns:
            Dict[symbol, dict]: 订单簿指标字典
                - spread: 买卖价差百分比 (越小流动性越好)
                - imbalance: 订单簿不平衡度 (-1 到 1，>0 表示买盘强，<0 表示卖盘强)
                - liquidity_depth: 前10档总流动性
                - bid_volume_10: 买单总量 (前10档)
                - ask_volume_10: 卖单总量 (前10档)
        """
        order_book_metrics = {}
        
        # 检测回测模式
        is_backtest = self.stream_manager is None
        if is_backtest:
            logger.debug("📋 Backtest mode: skipping order book metrics")
            return {}
        
        logger.info(f"📖 Fetching order book metrics for {len(symbols)} symbols...")
        
        for symbol in symbols:
            try:
                # 检查缓存（60秒TTL）
                if self.cache:
                    cached_metrics = self.cache.get('orderbook', symbol)
                    if cached_metrics:
                        order_book_metrics[symbol] = cached_metrics
                        logger.debug(f"  {symbol}: using cached order book data")
                        continue
                
                # 限流
                if self.rate_limiter:
                    await self.rate_limiter.wait_if_needed()
                
                # 获取订单簿（前20档）
                order_book = await self.trader.exchange.fetch_order_book(symbol, limit=20)
                
                bids = order_book.get('bids', [])
                asks = order_book.get('asks', [])
                
                if not bids or not asks:
                    logger.warning(f"  {symbol}: empty order book")
                    continue
                
                # 计算指标
                bid_price = bids[0][0]  # 最高买价
                ask_price = asks[0][0]  # 最低卖价
                
                # 买卖价差百分比
                spread = (ask_price - bid_price) / bid_price if bid_price > 0 else 0
                
                # 前10档流动性
                bid_volume_10 = sum([bid[1] for bid in bids[:10]]) if len(bids) >= 10 else sum([bid[1] for bid in bids])
                ask_volume_10 = sum([ask[1] for ask in asks[:10]]) if len(asks) >= 10 else sum([ask[1] for ask in asks])
                
                # 订单簿不平衡度（-1 到 1）
                total_volume = bid_volume_10 + ask_volume_10
                imbalance = (bid_volume_10 - ask_volume_10) / total_volume if total_volume > 0 else 0
                
                # 总流动性深度
                liquidity_depth = total_volume
                
                metrics = {
                    'spread': spread,
                    'imbalance': imbalance,
                    'liquidity_depth': liquidity_depth,
                    'bid_volume_10': bid_volume_10,
                    'ask_volume_10': ask_volume_10
                }
                
                order_book_metrics[symbol] = metrics
                
                # 缓存60秒
                if self.cache:
                    self.cache.set('orderbook', metrics, symbol)
                
                logger.debug(
                    f"  {symbol}: spread={spread*100:.4f}%, imbalance={imbalance:.2f}, "
                    f"liquidity={liquidity_depth:.2f}"
                )
            
            except Exception as e:
                logger.error(f"  {symbol}: failed to fetch order book: {e}")
                continue
        
        logger.info(f"✅ Fetched order book metrics for {len(order_book_metrics)}/{len(symbols)} symbols")
        return order_book_metrics
    
    async def _fetch_trade_metrics(self, symbols: List[str]) -> Dict[str, dict]:
        """
        批量获取最近成交记录指标
        
        Returns:
            Dict[symbol, dict]: 成交记录指标字典
                - buy_sell_ratio: 主动买卖比 (>1 表示买盘强，<1 表示卖盘强)
                - trade_intensity: 成交密集度 (笔/秒)
                - avg_trade_size: 平均成交规模
                - price_momentum: 价格动量 (最近成交价格变化百分比)
        """
        trade_metrics = {}
        
        # 检测回测模式
        is_backtest = self.stream_manager is None
        if is_backtest:
            logger.debug("📋 Backtest mode: skipping trade metrics")
            return {}
        
        logger.info(f"💹 Fetching trade metrics for {len(symbols)} symbols...")
        
        for symbol in symbols:
            try:
                # 检查缓存（60秒TTL）
                if self.cache:
                    cached_metrics = self.cache.get('trades', symbol)
                    if cached_metrics:
                        trade_metrics[symbol] = cached_metrics
                        logger.debug(f"  {symbol}: using cached trade data")
                        continue
                
                # 限流
                if self.rate_limiter:
                    await self.rate_limiter.wait_if_needed()
                
                # 获取最近100笔成交
                # Hyperliquid 需要额外的 user 参数
                params = {}
                if self.trader.exchange_name == 'hyperliquid':
                    params['user'] = self.trader.exchange_cfg.get('apikey')
                
                trades = await self.trader.exchange.fetch_trades(symbol, limit=100, params=params)
                
                if not trades or len(trades) < 10:
                    logger.warning(f"  {symbol}: insufficient trade data ({len(trades) if trades else 0} trades)")
                    continue
                
                # 计算主动买卖比（如果交易所支持side字段）
                buy_volume = 0
                sell_volume = 0
                total_volume = 0
                
                for trade in trades:
                    amount = trade.get('amount', 0)
                    total_volume += amount
                    
                    # 部分交易所提供side字段（buy/sell）
                    side = trade.get('side')
                    if side == 'buy':
                        buy_volume += amount
                    elif side == 'sell':
                        sell_volume += amount
                    else:
                        # 如果没有side字段，尝试通过takerOrMaker判断
                        # 但这不是标准方法，所以我们按50/50分配
                        buy_volume += amount / 2
                        sell_volume += amount / 2
                
                # 买卖比
                buy_sell_ratio = buy_volume / sell_volume if sell_volume > 0 else 1.0
                
                # 成交密集度（笔/秒）
                first_ts = trades[0].get('timestamp', 0)
                last_ts = trades[-1].get('timestamp', 0)
                time_span_sec = (last_ts - first_ts) / 1000 if last_ts > first_ts else 1
                trade_intensity = len(trades) / time_span_sec if time_span_sec > 0 else 0
                
                # 平均成交规模
                avg_trade_size = total_volume / len(trades) if len(trades) > 0 else 0
                
                # 价格动量（最近成交价格变化）
                first_price = trades[0].get('price', 0)
                last_price = trades[-1].get('price', 0)
                price_momentum = (last_price - first_price) / first_price if first_price > 0 else 0
                
                metrics = {
                    'buy_sell_ratio': buy_sell_ratio,
                    'trade_intensity': trade_intensity,
                    'avg_trade_size': avg_trade_size,
                    'price_momentum': price_momentum
                }
                
                trade_metrics[symbol] = metrics
                
                # 缓存60秒
                if self.cache:
                    self.cache.set('trades', metrics, symbol)
                
                logger.debug(
                    f"  {symbol}: buy/sell={buy_sell_ratio:.2f}, intensity={trade_intensity:.2f}/s, "
                    f"momentum={price_momentum*100:.2f}%"
                )
            
            except Exception as e:
                logger.error(f"  {symbol}: failed to fetch trades: {e}")
                continue
        
        logger.info(f"✅ Fetched trade metrics for {len(trade_metrics)}/{len(symbols)} symbols")
        return trade_metrics
    
    async def _get_klines(self, state: State):
        """
        获取 K 线数据（优先使用缓存，避免冗余 API 请求）
        
        优化策略：
        1. 优先从 stream_manager（WebSocket）获取
        2. 其次从 Cache 获取（coins_pick 阶段可能已缓存）
        3. 最后才回退到 REST API
        
        Cache 已内置 TTL 机制，无需额外的时间戳检查。
        """
        market_data = {}
        
        # 回测模式检测：stream_manager=None 表示回测模式
        is_backtest = self.stream_manager is None
        
        # 获取时间框架配置（向后兼容）
        timeframes = self.bot_config.timeframes if self.bot_config else ['3m', '4h']
        
        for symbol in state.symbols:
            symbol_data = {}
            
            for timeframe in timeframes:
                limit = self.bot_config.get_ohlcv_limit(timeframe) if self.bot_config else 100
                cache_key = f'{symbol}:{timeframe}:{limit}'
                cache_type = f'ohlcv_{timeframe}'
                
                ohlcv = None
                
                # 1. 优先从 stream_manager 获取（实盘 WebSocket）
                if self.stream_manager:
                    ohlcv = await self.stream_manager.get_latest_ohlcv(symbol, timeframe)
                
                # 2. 其次从 Cache 获取（Cache.get() 内置 TTL 检查）
                if not ohlcv and self.cache:
                    ohlcv = self.cache.get(cache_type, cache_key)
                    if ohlcv:
                        logger.debug(f"📦 {symbol} {timeframe} from cache")
                
                # 3. 缓存未命中或无效，回退到 REST API
                if not ohlcv or len(ohlcv) == 0:
                    if is_backtest:
                        # 回测模式：数据必须预加载，跳过 API 请求
                        logger.debug(f"📋 {symbol} {timeframe} no data in backtest mode")
                        continue
                    
                    try:
                        if self.rate_limiter:
                            await self.rate_limiter.wait_if_needed()
                        ohlcv = await self.trader.fetch_ohlcv(symbol, timeframe, limit=limit)
                        if ohlcv and self.cache:
                            self.cache.set(cache_type, ohlcv, cache_key)
                            logger.debug(f"🔄 {symbol} {timeframe} fetched and cached")
                    except Exception as e:
                        logger.error(f"Failed to fetch {timeframe} data for {symbol}: {e}")
                        continue
                
                if ohlcv and len(ohlcv) > 0:
                    symbol_data[timeframe] = ohlcv
            
            if symbol_data:
                market_data[symbol] = symbol_data
        
        return market_data
    
    def _timeframe_to_minutes(self, timeframe: str) -> int:
        """
        将时间框架转换为分钟数
        
        Args:
            timeframe: 时间框架字符串（如 '3m', '1h', '4h'）
            
        Returns:
            分钟数
        """
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        
        multipliers = {
            'm': 1,
            'h': 60,
            'd': 1440,
            'w': 10080
        }
        
        return value * multipliers.get(unit, 1)

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
        
        # ✅ 批量获取订单簿和成交记录指标（新增）
        order_book_metrics = {}
        trade_metrics = {}
        
        # 检测回测模式 - 只在实盘模式下获取
        is_backtest = self.stream_manager is None
        if not is_backtest:
            order_book_metrics = await self._fetch_order_book_metrics(symbols)
            trade_metrics = await self._fetch_trade_metrics(symbols)
            logger.info(f"📊 Fetched advanced metrics: orderbook={len(order_book_metrics)}, trades={len(trade_metrics)}")
        else:
            logger.debug("📋 Backtest mode: skipping order book and trade metrics")

        for symbol, data in k_market_data.items():
            indicators = {}

            try:
                # 动态计算各时间框架的指标
                timeframes = self.bot_config.timeframes if self.bot_config else ['3m', '4h']
                
                # 获取指标配置（向后兼容）
                if self.bot_config:
                    ema_periods = self.bot_config.get_ema_periods()
                    rsi_period = self.bot_config.get_rsi_period()
                    atr_period = self.bot_config.get_atr_period()
                    bollinger_config = self.bot_config.get_bollinger_config()
                    stochastic_config = self.bot_config.get_stochastic_config()
                else:
                    # 默认配置
                    ema_periods = [20, 50, 200]
                    rsi_period = 7
                    atr_period = 14
                    bollinger_config = {"period": 20, "std": 2.0}
                    stochastic_config = {"k": 14, "d": 3}
                
                # 为每个时间框架计算指标
                for timeframe in timeframes:
                    if timeframe in data and data[timeframe]:
                        klines = ohlcv_to_klines(data[timeframe])
                        tf_suffix = f"_{timeframe}"
                        
                        # 基础指标
                        for period in ema_periods:
                            indicators[f'ema_{period}{tf_suffix}'] = self.calc.calculate_ema(klines, period)
                        
                        indicators[f'macd{tf_suffix}'] = self.calc.calculate_macd(klines)
                        indicators[f'rsi{tf_suffix}'] = self.calc.calculate_rsi(klines, rsi_period)
                        indicators[f'atr{tf_suffix}'] = self.calc.calculate_atr(klines, atr_period)
                        
                        # 高级指标
                        indicators[f'bollinger{tf_suffix}'] = self.calc.calculate_bollinger_bands(
                            klines, 
                            bollinger_config["period"], 
                            bollinger_config["std"]
                        )
                        indicators[f'atr_percent{tf_suffix}'] = self.calc.calculate_atr_percent(klines, atr_period)
                        indicators[f'stochastic{tf_suffix}'] = self.calc.calculate_stochastic(
                            klines,
                            stochastic_config["k"],
                            stochastic_config["d"]
                        )
                        indicators[f'obv{tf_suffix}'] = self.calc.calculate_obv(klines)
                        
                        # 短周期特有指标
                        if timeframe in ['3m', '5m', '15m']:
                            indicators[f'vwap{tf_suffix}'] = self.calc.calculate_vwap(klines)
                            indicators[f'volume_ratio{tf_suffix}'] = self.calc.calculate_volume_ratio(klines, 20)
                            
                            # 实时价格（仅第一个时间框架）
                            if timeframe == timeframes[0]:
                                kline_price = klines[-1].close if klines else 0
                                realtime_price = realtime_prices.get(symbol, 0)
                                indicators['current_price'] = realtime_price if realtime_price > 0 else kline_price
                                indicators['kline_price'] = kline_price
                        
                        # 长周期特有指标
                        if timeframe in ['4h', '1d']:
                            indicators[f'adx{tf_suffix}'] = self.calc.calculate_adx(klines, 14)
                
                # 添加资金费率到指标
                indicators['funding_rate'] = funding_rates.get(symbol, 0)
                
                # 添加订单簿指标（新增）
                if symbol in order_book_metrics:
                    indicators.update(order_book_metrics[symbol])
                
                # 添加成交记录指标（新增）
                if symbol in trade_metrics:
                    indicators.update(trade_metrics[symbol])
                
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

        
        # 动态统计信息
        timeframes = self.bot_config.timeframes if self.bot_config else ['3m', '4h']
        logger.info(f"✅ Market data ready: {len(market_data)}/{len(state.symbols)} symbols")
        
        for tf in timeframes:
            count = sum(1 for v in market_data.values() if v.get(tf))
            logger.info(f"   {tf} data: {count}/{len(state.symbols)}")

        return market_data
