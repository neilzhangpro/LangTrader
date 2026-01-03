"""
动态 WebSocket 流管理器
根据选币结果自动订阅/取消订阅，优化资源使用和数据实时性
"""
from typing import Dict, Set, Optional, List
import asyncio
from collections import defaultdict
import time
from langtrader_core.services.trader import Trader
from langtrader_core.services.cache import Cache
from langtrader_core.utils import get_logger

logger = get_logger("stream_manager")


class DynamicStreamManager:
    """
    动态 WebSocket 流管理器
    - 根据选币结果自动订阅/取消订阅
    - 支持多时间框架
    - 自动维护连接和重连
    """
    
    def __init__(self, trader: Trader):
        self.trader = trader
        self.cache = Cache()
        
        # 订阅状态追踪
        self.active_subscriptions: Dict[str, Dict[str, asyncio.Task]] = defaultdict(dict)
        # 格式: {symbol: {timeframe: task}}
        
        # 订阅锁（避免重复订阅）
        self._subscription_locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        
        # 失败币种追踪（用于下一轮重试）
        self._failed_symbols: Set[str] = set()
        
        # 统计信息
        self.stats = {
            'total_subscribed': 0,
            'total_unsubscribed': 0,
            'active_streams': 0,
            'reconnections': 0,
            'failed_retries': 0
        }
    
    async def sync_subscriptions(
        self, 
        new_symbols: List[str], 
        timeframes: List[str] = ['3m']
    ):
        """
        同步订阅列表（核心方法）
        根据新的币种列表，自动添加/删除订阅
        
        Args:
            new_symbols: 最新的选币结果
            timeframes: 要订阅的时间框架列表
        """
        new_set = set(new_symbols)
        current_set = set(self.active_subscriptions.keys())
        
        # 将之前失败的币种（如果仍在候选列表中）加入重新订阅
        retry_symbols = self._failed_symbols & new_set
        if retry_symbols:
            logger.info(f"🔄 Re-attempting {len(retry_symbols)} previously failed symbols")
            self._failed_symbols.clear()
        
        # 计算差异（包含需要重试的币种）
        to_subscribe = (new_set - current_set) | retry_symbols
        to_unsubscribe = current_set - new_set
        to_keep = current_set & new_set - retry_symbols
        
        logger.info(f"📊 Subscription sync: "
                   f"+{len(to_subscribe)} "
                   f"-{len(to_unsubscribe)} "
                   f"={len(to_keep)}")
        
        # 并发处理订阅变化
        tasks = []
        
        # 1. 取消不需要的订阅
        for symbol in to_unsubscribe:
            tasks.append(self._unsubscribe_symbol(symbol))
        
        # 2. 添加新订阅（带速率限制）
        for idx, symbol in enumerate(to_subscribe):
            for timeframe in timeframes:
                # 添加小延迟避免订阅风暴
                if idx > 0:
                    await asyncio.sleep(0.1)
                tasks.append(self._subscribe(symbol, timeframe))
        
        # 等待所有操作完成
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                logger.warning(f"⚠️  {len(errors)} subscription operations failed")
                for error in errors:
                    logger.debug(f"Error detail: {error}")
        
        # 更新统计
        self.stats['active_streams'] = len(self.active_subscriptions)
        logger.info(f"✅ Active streams: {self.stats['active_streams']} symbols")
        
        # 显示当前订阅的币种列表
        if self.active_subscriptions:
            symbols_list = list(self.active_subscriptions.keys())[:5]  # 显示前5个
            if len(self.active_subscriptions) > 5:
                symbols_list.append(f"... (+{len(self.active_subscriptions) - 5} more)")
            logger.info(f"   Symbols: {', '.join(symbols_list)}")
    
    async def _subscribe(self, symbol: str, timeframe: str):
        """
        订阅单个币种的 OHLCV 流
        首次订阅时会使用 REST API 预填充缓存，避免冷启动问题
        """
        async with self._subscription_locks[f"{symbol}:{timeframe}"]:
            # 检查是否已订阅
            if timeframe in self.active_subscriptions.get(symbol, {}):
                logger.debug(f"Already subscribed: {symbol} {timeframe}")
                return
            
            logger.info(f"📡 Subscribing: {symbol} {timeframe}")
            
            try:
                # ✅ 首次订阅：先用 REST API 预填充缓存（避免冷启动）
                cache_key = f'{symbol}:{timeframe}:100'
                cached_data = self.cache.get(f'ohlcv_{timeframe}', cache_key)
                
                if not cached_data:
                    logger.debug(f"🔄 Pre-filling cache for {symbol} {timeframe}")
                    try:
                        initial_ohlcv = await self.trader.fetch_ohlcv(symbol, timeframe, limit=100)
                        if initial_ohlcv:
                            self.cache.set(f'ohlcv_{timeframe}', initial_ohlcv, cache_key)
                            logger.debug(f"✅ Cache pre-filled: {symbol} {timeframe} ({len(initial_ohlcv)} candles)")
                    except Exception as e:
                        logger.warning(f"Failed to pre-fill cache for {symbol}: {e}")
                
                # 创建 WebSocket 监听任务
                task = asyncio.create_task(
                    self._watch_stream(symbol, timeframe),
                    name=f"watch_{symbol}_{timeframe}"
                )
                
                self.active_subscriptions[symbol][timeframe] = task
                self.stats['total_subscribed'] += 1
                
            except Exception as e:
                logger.error(f"Failed to subscribe {symbol} {timeframe}: {e}")
                raise
    
    async def _unsubscribe_symbol(self, symbol: str):
        """
        取消订阅整个币种的所有时间框架
        """
        if symbol not in self.active_subscriptions:
            return
        
        logger.info(f"🔌 Unsubscribing: {symbol}")
        
        # 取消所有时间框架的订阅
        tasks = self.active_subscriptions[symbol]
        
        for timeframe, task in tasks.items():
            try:
                # 调用 CCXT 的 unwatch_ohlcv（如果支持）
                if hasattr(self.trader.exchange, 'unwatch_ohlcv'):
                    try:
                        await self.trader.exchange.unwatch_ohlcv(symbol, timeframe)
                        logger.debug(f"Called unwatch_ohlcv for {symbol} {timeframe}")
                    except Exception as e:
                        logger.debug(f"unwatch_ohlcv not supported or failed: {e}")
                
                # 取消协程任务
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                self.stats['total_unsubscribed'] += 1
                
            except Exception as e:
                logger.error(f"Error unsubscribing {symbol} {timeframe}: {e}")
        
        # 从活跃列表中删除
        del self.active_subscriptions[symbol]
        
        # 清理相关缓存
        self._cleanup_cache(symbol)
        
        # 清理对应的订阅锁（避免内存泄漏）
        lock_keys_to_remove = [k for k in list(self._subscription_locks.keys()) 
                              if k.startswith(f"{symbol}:")]
        for key in lock_keys_to_remove:
            del self._subscription_locks[key]
        if lock_keys_to_remove:
            logger.debug(f"🔓 Cleaned up {len(lock_keys_to_remove)} locks for {symbol}")
    
    async def _watch_stream(self, symbol: str, timeframe: str):
        """
        持续监听单个币种的 OHLCV 流
        支持自动重连
        只在K线完成时更新缓存，避免使用未完成的K线计算指标
        """
        retry_count = 0
        max_retries = 5
        last_candle_time = None  # 跟踪最后一根已完成K线的时间
        
        while True:
            try:
                logger.debug(f"📊 Watching {symbol} {timeframe}...")
                
                # CCXT Pro 的 watch_ohlcv 会持续返回更新
                ohlcv = await self.trader.exchange.watch_ohlcv(symbol, timeframe)
                
                if not ohlcv or len(ohlcv) == 0:
                    continue
                
                # 获取最新K线
                latest_candle = ohlcv[-1]
                candle_open_time = latest_candle[0]  # 开盘时间戳（毫秒）
                
                # 计算K线关闭时间
                timeframe_ms = self._timeframe_to_ms(timeframe)
                candle_close_time = candle_open_time + timeframe_ms
                current_time = int(time.time() * 1000)  # 当前时间（毫秒）
                
                # 判断K线是否已完成
                is_completed = current_time >= candle_close_time
                
                # 检查是否是新的完成K线（避免重复更新同一根K线）
                is_new_candle = last_candle_time is None or candle_open_time > last_candle_time
                
                if is_completed and is_new_candle:
                    # K线已完成，更新缓存
                    cache_key = f'{symbol}:{timeframe}:100'
                    self.cache.set(f'ohlcv_{timeframe}', ohlcv, cache_key)
                    
                    last_candle_time = candle_open_time
                    logger.debug(f"✅ Updated completed candle: {symbol} {timeframe} at {candle_open_time}")
                elif not is_completed:
                    # ✅ 实时更新：即使K线未完成，也更新缓存以提供最新价格
                    cache_key = f'{symbol}:{timeframe}:100'
                    self.cache.set(f'ohlcv_{timeframe}', ohlcv, cache_key)
                    logger.debug(f"📡 Updated partial candle (real-time): {symbol} {timeframe} "
                               f"(close in {(candle_close_time - current_time) / 1000:.0f}s)")
                else:
                    # K线已完成但不是新K线，跳过更新
                    pass
                
                # 日志记录（降低频率，避免刷屏）
                if retry_count > 0:
                    logger.info(f"✅ Reconnected: {symbol} {timeframe}")
                
                # 重置重试计数
                retry_count = 0
                
            except asyncio.CancelledError:
                logger.info(f"Stream cancelled: {symbol} {timeframe}")
                break
                
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ Stream error {symbol} {timeframe}: {e} "
                           f"(retry {retry_count}/{max_retries})")
                
                if retry_count >= max_retries:
                    logger.error(f"Max retries reached for {symbol} {timeframe}, giving up")
                    # 从活跃订阅中移除
                    if symbol in self.active_subscriptions:
                        self.active_subscriptions[symbol].pop(timeframe, None)
                        if not self.active_subscriptions[symbol]:
                            del self.active_subscriptions[symbol]
                    
                    # 标记为失败，下一轮 sync_subscriptions 时会尝试重新订阅
                    self._failed_symbols.add(symbol)
                    self.stats['failed_retries'] += 1
                    logger.info(f"📌 Marked {symbol} for retry in next sync cycle")
                    break
                
                # 指数退避重试
                backoff_time = min(2 ** retry_count, 60)
                logger.info(f"Retrying in {backoff_time}s...")
                await asyncio.sleep(backoff_time)
                self.stats['reconnections'] += 1
    
    def _timeframe_to_ms(self, timeframe: str) -> int:
        """
        将时间框架转换为毫秒
        
        Args:
            timeframe: 时间框架字符串，如 '3m', '1h', '1d'
            
        Returns:
            时间框架对应的毫秒数
        """
        unit = timeframe[-1]
        value = int(timeframe[:-1])
        
        multipliers = {
            's': 1000,           # 秒
            'm': 60 * 1000,      # 分钟
            'h': 3600 * 1000,    # 小时
            'd': 86400 * 1000,   # 天
            'w': 7 * 86400 * 1000,  # 周
        }
        
        if unit not in multipliers:
            logger.warning(f"Unknown timeframe unit: {unit}, defaulting to minutes")
            return value * 60 * 1000
        
        return value * multipliers[unit]
    
    def _cleanup_cache(self, symbol: str):
        """清理币种相关的缓存"""
        for timeframe in ['3m', '4h', '1h', '15m']:
            cache_key = f'{symbol}:{timeframe}:100'
            try:
                # 使用 Cache 的 delete 方法清理
                self.cache.delete(f'ohlcv_{timeframe}', cache_key)
            except Exception as e:
                logger.debug(f"Cache cleanup error for {symbol}: {e}")
    
    async def get_latest_ohlcv(self, symbol: str, timeframe: str) -> Optional[list]:
        """
        获取最新的 OHLCV 数据
        优先从缓存读取（WebSocket 实时更新的）
        
        Args:
            symbol: 交易对符号
            timeframe: 时间框架
            
        Returns:
            OHLCV 数据列表，如果不可用则返回 None
        """
        cache_key = f'{symbol}:{timeframe}:100'
        data = self.cache.get(f'ohlcv_{timeframe}', cache_key)
        
        if data:
            logger.debug(f"Cache hit for {symbol} {timeframe}")
            return data
        
        # 如果缓存未命中，回退到 REST API
        logger.warning(f"Cache miss for {symbol} {timeframe}, falling back to REST")
        try:
            return await self.trader.fetch_ohlcv(symbol, timeframe, limit=100)
        except Exception as e:
            logger.error(f"Failed to fetch OHLCV for {symbol} {timeframe}: {e}")
            return None
    
    async def shutdown(self):
        """
        优雅关闭所有订阅
        """
        logger.info("🛑 Shutting down all streams...")
        
        symbols = list(self.active_subscriptions.keys())
        tasks = [self._unsubscribe_symbol(symbol) for symbol in symbols]
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"✅ Shutdown complete. Stats: {self.stats}")
    
    def get_stats(self) -> dict:
        """获取订阅统计信息"""
        return {
            **self.stats,
            'current_symbols': list(self.active_subscriptions.keys()),
            'subscriptions_detail': {
                symbol: list(subs.keys()) 
                for symbol, subs in self.active_subscriptions.items()
            }
        }

