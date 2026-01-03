"""
限流服务（单例模式）

为 API 调用提供间隔限流和时间窗口限流。
"""
import asyncio
from collections import deque

from langtrader_core.services.singleton import Singleton
from langtrader_core.utils import get_logger

logger = get_logger("rate_limiter")


class RateLimiter(Singleton):
    """
    异步限流器（单例模式）
    
    支持两种限流策略：
    1. 间隔限流：连续请求之间的最小间隔
    2. 窗口限流：时间窗口内的最大请求数
    """
    
    def _init_singleton(self):
        """初始化限流器"""
        # 间隔限流
        self._last_request_time = 0
        self._rate_limit_seconds = 0
        
        # 窗口限流
        self._request_times = deque()
        self._max_requests_per_minute = 20
        self._time_window = 60
        
        self._async_lock = asyncio.Lock()
        logger.info("RateLimiter singleton initialized")
    
    def set_rate_limit(self, rate_limit_ms: int):
        """
        Set the minimum interval between requests in milliseconds
        
        Args:
            rate_limit_ms: Rate limit in milliseconds
        """
        calculated_limit = rate_limit_ms / 1000
        # Reduced to 0.5 seconds for better throughput with concurrent requests
        self._rate_limit_seconds = max(calculated_limit, 0.5)
        logger.info(f"Rate limit set to {self._rate_limit_seconds:.3f}s (calculated: {calculated_limit}s)")
        logger.info(f"Time window limit: max {self._max_requests_per_minute} requests per {self._time_window} seconds")
    
    async def wait_if_needed(self):
        """
        异步等待（如果需要）
        同时执行间隔限流和窗口限流检查
        """
        async with self._async_lock:
            # Use asyncio event loop time for consistency
            loop = asyncio.get_event_loop()
            current_time = loop.time()
            
            # Step 1: Remove expired requests from the time window
            while self._request_times and current_time - self._request_times[0] > self._time_window:
                self._request_times.popleft()
            
            # Step 2: Check if we've exceeded the time window limit
            if len(self._request_times) >= self._max_requests_per_minute:
                # Time window limit exceeded, need to wait
                oldest_request_time = self._request_times[0]
                wait_time = self._time_window - (current_time - oldest_request_time) + 0.1  # Add 0.1s buffer
                
                logger.warning(
                    f"⚠️  Time window limit exceeded: {len(self._request_times)} requests in last {self._time_window}s. "
                    f"Waiting {wait_time:.1f}s until oldest request expires..."
                )
                await asyncio.sleep(wait_time)
                current_time = loop.time()
                
                # Clean up expired requests again after waiting
                while self._request_times and current_time - self._request_times[0] > self._time_window:
                    self._request_times.popleft()
            
            # Step 3: Check interval-based rate limit
            time_since_last_request = current_time - self._last_request_time
            if time_since_last_request < self._rate_limit_seconds:
                sleep_time = self._rate_limit_seconds - time_since_last_request
                logger.debug(
                    f"Rate limit protection: sleeping for {sleep_time:.3f} seconds "
                    f"(limit: {self._rate_limit_seconds:.3f}s, elapsed: {time_since_last_request:.3f}s)"
                )
                await asyncio.sleep(sleep_time)
                current_time = loop.time()
            
            # Step 4: Record this request
            self._last_request_time = current_time
            self._request_times.append(current_time)
            
            logger.debug(
                f"✓ Request approved. "
                f"Requests in last {self._time_window}s: {len(self._request_times)}/{self._max_requests_per_minute}"
            )