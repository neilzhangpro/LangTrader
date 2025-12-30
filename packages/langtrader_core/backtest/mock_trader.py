# packages/langtrader_core/backtest/mock_trader.py
"""
模拟交易器 - 用于回测
完全模拟 Trader 接口但不与真实交易所交互
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
import asyncio
from langtrader_core.graph.state import Account, Position, OrderResult, OpenPositionResult
from langtrader_core.utils import get_logger

logger = get_logger("mock_trader")


class BacktestDataSource:
    """
    回测数据源抽象基类
    """
    
    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        cache: Optional[Any] = None
    ):
        self.start_time = int(start_time.timestamp() * 1000)
        self.end_time = int(end_time.timestamp() * 1000)
        self.current_time = self.start_time
        
        # 复用现有 Cache
        from langtrader_core.services.cache import Cache as CacheClass
        self.cache = cache if cache else CacheClass()
    
    async def get_ohlcv(
        self, 
        symbol: str, 
        timeframe: str,
        limit: int = 100
    ) -> List[List]:
        """获取K线数据"""
        raise NotImplementedError
    
    async def get_funding_rates(self, symbols: List[str]) -> Dict[str, float]:
        """获取资金费率"""
        raise NotImplementedError
    
    async def get_markets(self) -> Dict:
        """获取市场信息"""
        raise NotImplementedError
    
    def advance_time(self, delta_ms: int):
        """推进时间"""
        self.current_time += delta_ms
    
    def has_more_data(self) -> bool:
        """是否还有更多数据"""
        return self.current_time < self.end_time


class ExchangeBacktestDataSource(BacktestDataSource):
    """
    从交易所拉取历史数据（优先实现）
    
    设计特点：
    1. 利用现有 Cache 减少 API 请求
    2. 批量拉取数据（一次拉取整个回测期间）
    3. 支持 RateLimiter
    """
    
    def __init__(
        self,
        start_time: datetime,
        end_time: datetime,
        exchange,
        cache: Optional[Any] = None,
        rate_limiter: Optional[Any] = None
    ):
        super().__init__(start_time, end_time, cache)
        self.exchange = exchange
        self.rate_limiter = rate_limiter
        
        # 预加载数据缓存
        self.preloaded_data = {}
        
        # 🔧 历史资金费率存储: {symbol: {timestamp_ms: funding_rate}}
        self.funding_rate_history: Dict[str, Dict[int, float]] = {}
    
    async def preload_data(
        self, 
        symbols: List[str], 
        timeframes: List[str],
        since: Optional[datetime] = None
    ):
        """
        预加载所有回测数据（减少API请求）
        
        Args:
            symbols: 要预加载的交易对列表
            timeframes: 时间周期列表
            since: 预加载起始时间（可选，默认使用回测开始时间）
                   可用于提前加载更多历史数据（如 EMA 200 需要约35天4h数据）
        """
        # 🔧 使用传入的 since 或默认使用回测开始时间
        preload_since_ms = int(since.timestamp() * 1000) if since else self.start_time
        
        logger.info(f"📦 Preloading backtest data...")
        logger.info(f"   Symbols: {len(symbols)}")
        logger.info(f"   Timeframes: {timeframes}")
        logger.info(f"   Preload from: {datetime.fromtimestamp(preload_since_ms/1000)}")
        logger.info(f"   Backtest period: {datetime.fromtimestamp(self.start_time/1000)} → {datetime.fromtimestamp(self.end_time/1000)}")
        
        async def fetch_one(symbol, timeframe):
            cache_key = f"{symbol}:{timeframe}"
            
            # 检查缓存
            cached = self.cache.get('backtest_ohlcv', cache_key)
            if cached:
                logger.debug(f"✓ Cached: {cache_key}")
                return (symbol, timeframe, cached)
            
            # 限流
            if self.rate_limiter:
                await self.rate_limiter.wait_if_needed()
            
            try:
                # 从交易所拉取（使用扩展的 since 时间）
                ohlcv = await self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe,
                    since=preload_since_ms,
                    limit=5000  # 拉取足够多的数据
                )
                
                # 缓存（长TTL）
                self.cache.set('backtest_ohlcv', ohlcv, cache_key)
                logger.info(f"✓ Fetched: {cache_key} ({len(ohlcv)} candles)")
                
                return (symbol, timeframe, ohlcv)
                
            except Exception as e:
                logger.error(f"✗ Failed: {cache_key} - {e}")
                return (symbol, timeframe, [])
        
        # 并发拉取（控制并发数）
        semaphore = asyncio.Semaphore(5)
        
        async def fetch_with_semaphore(symbol, timeframe):
            async with semaphore:
                return await fetch_one(symbol, timeframe)
        
        tasks = [
            fetch_with_semaphore(symbol, timeframe)
            for symbol in symbols
            for timeframe in timeframes
        ]
        
        results = await asyncio.gather(*tasks)
        
        # 组织数据
        for symbol, timeframe, ohlcv in results:
            if symbol not in self.preloaded_data:
                self.preloaded_data[symbol] = {}
            self.preloaded_data[symbol][timeframe] = ohlcv
        
        # 🔧 将预加载数据同步到 Cache，供 coin.py 等服务使用
        for symbol in symbols:
            for timeframe in timeframes:
                ohlcv_data = self.preloaded_data.get(symbol, {}).get(timeframe, [])
                if ohlcv_data:
                    # 使用与 coin.py 相同的缓存 key 格式
                    cache_key = f'{symbol}:{timeframe}:100'
                    cache_type = f'ohlcv_{timeframe}'
                    self.cache.set(cache_type, ohlcv_data, cache_key)
                    logger.debug(f"✓ Synced to cache: {cache_type}/{cache_key}")
        
        # 🔧 预加载历史资金费率
        await self._preload_funding_rates(symbols)
        
        logger.info(f"✅ Preloaded data for {len(symbols)} symbols")
    
    async def _preload_funding_rates(self, symbols: List[str]):
        """
        预加载历史资金费率
        使用 CCXT fetchFundingRateHistory API
        """
        logger.info(f"💰 Preloading funding rate history...")
        
        # 检查交易所是否支持
        if not self.exchange.has.get('fetchFundingRateHistory'):
            logger.warning("⚠️ Exchange does not support fetchFundingRateHistory, using 0")
            for symbol in symbols:
                self.funding_rate_history[symbol] = {}
            return
        
        semaphore = asyncio.Semaphore(3)  # 限制并发
        
        async def fetch_one(symbol: str):
            async with semaphore:
                try:
                    if self.rate_limiter:
                        await self.rate_limiter.wait_if_needed()
                    
                    # 获取历史资金费率
                    rates = await self.exchange.fetchFundingRateHistory(
                        symbol,
                        since=self.start_time,
                        limit=1000  # 获取足够多的历史数据
                    )
                    
                    # 转换为 {timestamp: rate} 格式
                    rate_map = {}
                    for rate in rates:
                        ts = rate.get('timestamp', 0)
                        funding_rate = rate.get('fundingRate', 0)
                        if ts and funding_rate is not None:
                            rate_map[ts] = float(funding_rate)
                    
                    logger.debug(f"✓ {symbol}: {len(rate_map)} funding rate records")
                    return (symbol, rate_map)
                    
                except Exception as e:
                    logger.warning(f"✗ Failed to fetch funding rates for {symbol}: {e}")
                    return (symbol, {})
        
        tasks = [fetch_one(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        
        for symbol, rate_map in results:
            self.funding_rate_history[symbol] = rate_map
        
        total_records = sum(len(v) for v in self.funding_rate_history.values())
        logger.info(f"✅ Preloaded {total_records} funding rate records for {len(symbols)} symbols")
    
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[List]:
        """获取K线（从预加载数据切片）"""
        if symbol not in self.preloaded_data:
            return []
        
        all_ohlcv = self.preloaded_data.get(symbol, {}).get(timeframe, [])
        
        # 根据 current_time 过滤数据
        filtered = [
            candle for candle in all_ohlcv
            if candle[0] <= self.current_time
        ]
        
        return filtered[-limit:] if len(filtered) >= limit else filtered
    
    async def get_funding_rates(self, symbols: List[str]) -> Dict[str, float]:
        """
        获取资金费率（从历史数据中查找最近的记录）
        找到 <= current_time 的最近一条记录
        """
        result = {}
        for symbol in symbols:
            history = self.funding_rate_history.get(symbol, {})
            if not history:
                result[symbol] = 0
                continue
            
            # 找到 <= current_time 的最大时间戳
            valid_timestamps = [ts for ts in history.keys() if ts <= self.current_time]
            if valid_timestamps:
                latest_ts = max(valid_timestamps)
                result[symbol] = history[latest_ts]
            else:
                result[symbol] = 0
        
        return result
    
    async def get_markets(self) -> Dict:
        """获取市场信息"""
        return await self.exchange.load_markets()


class MockTrader:
    """
    模拟交易器（用于回测）
    
    设计特点：
    1. 接口与 Trader 完全一致
    2. 维护虚拟账户余额
    3. 模拟订单撮合（基于下一根K线）
    4. 计算手续费和滑点
    """
    
    def __init__(
        self,
        initial_balance: float,
        data_source: BacktestDataSource,
        commission: float = 0.0005,  # 0.05% 手续费
        slippage: float = 0.0002,    # 0.02% 滑点
        performance_service: Optional[Any] = None  # MockPerformanceService
    ):
        self.initial_balance = initial_balance
        self.data_source = data_source
        self.commission = commission
        self.slippage = slippage
        self.performance_service = performance_service
        
        # 虚拟账户
        self.balance = initial_balance
        self.positions: Dict[str, Position] = {}
        
        # 模拟交易所属性（匹配 CCXT）
        self.exchange_name = "mock_exchange"
        self.markets = None
        # 🔧 修复：让 exchange 指向自身，这样其他代码可以访问 self.exchange.has
        self.exchange = self
        self.has = {
            'fetchOHLCV': True,
            'fetchFundingRates': True,
            'createOrder': True,
            'fetchOpenInterests': False,  # MockTrader 不支持持仓量查询
        }
        self._capabilities = {}
        # 模拟交易所的 rateLimit（毫秒）
        self.rateLimit = 50  # 模拟 50ms 的请求间隔
    
    async def async_init(self):
        """异步初始化（匹配 Trader 接口）"""
        logger.info("Initializing MockTrader...")
        self.markets = await self.data_source.get_markets()
        logger.info(f"✅ MockTrader initialized with {len(self.markets)} markets")
        return self
    
    async def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str, 
        limit: int = 100
    ) -> List[List]:
        """获取历史K线（从数据源）"""
        return await self.data_source.get_ohlcv(
            symbol, 
            timeframe,
            limit=limit
        )
    
    async def fetchFundingRates(self, symbols: List[str]) -> Dict:
        """获取历史资金费率"""
        rates_dict = await self.data_source.get_funding_rates(symbols)
        
        # 转换为 CCXT 格式
        result = {}
        for symbol, rate in rates_dict.items():
            result[symbol] = {
                'fundingRate': rate,
                'timestamp': self.data_source.current_time,
                'datetime': datetime.fromtimestamp(self.data_source.current_time / 1000).isoformat()
            }
        
        return result
    
    async def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        params: Dict = None,
        **kwargs
    ) -> Dict:
        """模拟下单"""
        current_price = await self._get_current_price(symbol)
        
        if current_price == 0:
            logger.error(f"❌ Cannot get price for {symbol}")
            raise ValueError(f"Cannot get price for {symbol}")
        
        # 计算成交价（考虑滑点）
        if side == "buy":
            fill_price = current_price * (1 + self.slippage)
        else:
            fill_price = current_price * (1 - self.slippage)
        
        # 计算手续费
        notional = amount * fill_price
        fee = notional * self.commission
        
        # 更新余额
        if side == "buy":
            self.balance -= (notional + fee)
        else:
            self.balance += (notional - fee)
        
        order = {
            "id": f"mock_{int(self.data_source.current_time)}",
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": amount,
            "filled": amount,
            "remaining": 0,
            "average": fill_price,
            "status": "closed",
            "fee": {"cost": fee},
            "timestamp": self.data_source.current_time,
        }
        
        logger.info(f"📝 Mock: {side} {amount} {symbol} @ {fill_price:.2f} (fee: {fee:.4f})")
        return order
    
    async def open_position(
        self,
        symbol: str,
        side: str,
        amount: float,
        leverage: int = 1,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "market",
        price: Optional[float] = None,
    ) -> OpenPositionResult:
        """模拟开仓"""
        main_order = await self.create_order(symbol, order_type, side, amount, price)
        
        position = Position(
            id=main_order["id"],
            symbol=symbol,
            side=side,
            type="market",
            status="open",
            datetime=datetime.fromtimestamp(main_order["timestamp"] / 1000),
            price=main_order["average"],
            average=main_order["average"],
            amount=amount,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
        )
        
        self.positions[symbol] = position
        
        return OpenPositionResult(
            main=self._parse_order_result(main_order)
        )
    
    async def close_position(
        self, 
        symbol: str, 
        amount: Optional[float] = None
    ) -> OrderResult:
        """模拟平仓"""
        if symbol not in self.positions:
            return OrderResult(success=False, error="No position found")
        
        position = self.positions[symbol]
        close_side = "sell" if position.side == "buy" else "buy"
        close_amount = amount or position.amount
        
        order = await self.create_order(symbol, "market", close_side, close_amount)
        
        # 🔧 记录交易到 MockPerformanceService
        if self.performance_service:
            self.performance_service.record_trade(
                symbol=symbol,
                side=position.side,
                entry_price=position.price,
                exit_price=order["average"],
                amount=close_amount,
                entry_time=int(position.datetime.timestamp() * 1000),
                exit_time=order["timestamp"]
            )
        
        del self.positions[symbol]
        
        return self._parse_order_result(order)
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """获取单个持仓"""
        return self.positions.get(symbol)
    
    async def get_positions(self, symbols: List[str] = None) -> List[Position]:
        """获取持仓列表"""
        if symbols:
            return [p for s, p in self.positions.items() if s in symbols]
        return list(self.positions.values())
    
    async def get_account_info(self) -> Account:
        """获取账户信息"""
        return Account(
            timestamp=datetime.now(),
            free={"USDT": self.balance},
            used={"USDT": 0},
            total={"USDT": self.balance},
            debt={"USDT": 0}
        )
    
    async def watch_tickers(self, symbols: List[str]) -> Dict:
        """模拟 watch_tickers（返回最新价格）"""
        tickers = {}
        for symbol in symbols:
            price = await self._get_current_price(symbol)
            tickers[symbol] = {
                'symbol': symbol,
                'last': price,
                'close': price,
                'bid': price * 0.9999,
                'ask': price * 1.0001,
                'timestamp': self.data_source.current_time,
            }
        return tickers
    
    async def fetch_ticker(self, symbol: str) -> Dict:
        """模拟 fetch_ticker - 从历史K线获取"当前"价格"""
        price = await self._get_current_price(symbol)
        return {
            'symbol': symbol,
            'last': price,
            'close': price,
            'bid': price * 0.9999,
            'ask': price * 1.0001,
            'high': price * 1.01,
            'low': price * 0.99,
            'timestamp': self.data_source.current_time,
        }
    
    async def fetch_tickers(self, symbols: List[str] = None) -> Dict:
        """模拟 fetch_tickers - 批量获取"""
        if symbols is None:
            symbols = list(self.markets.keys()) if self.markets else []
        
        tickers = {}
        for symbol in symbols:
            tickers[symbol] = await self.fetch_ticker(symbol)
        return tickers
    
    async def _get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        ohlcv = await self.fetch_ohlcv(symbol, "3m", limit=1)
        if ohlcv and len(ohlcv) > 0:
            return ohlcv[-1][4]  # close price
        return 0
    
    def _parse_order_result(self, order: Dict) -> OrderResult:
        """解析订单结果"""
        return OrderResult(
            success=True,
            order_id=order["id"],
            symbol=order["symbol"],
            status=order["status"],
            filled=order["filled"],
            remaining=order["remaining"],
            average=order["average"],
            fee=order["fee"]["cost"],
            raw=order
        )
    
    async def close(self):
        """关闭连接（空实现）"""
        pass


