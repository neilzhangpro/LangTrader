import asyncio
from collections import deque
from langtrader_core.utils import get_logger
logger = get_logger("rate_limiter")

class RateLimiter:
    """
    Async Rate limiter with time window management (Singleton pattern)
    Ensures all API calls comply with both:
    1. Interval limit: minimum time between consecutive requests
    2. Window limit: maximum requests within a time window
    """
    _instance = None  # Class instance to store the singleton instance
    _lock = None  # Async lock for thread-safe singleton creation

    def __new__(cls):
        """
        Create or return the singleton instance
        """
        if cls._instance is None:
            cls._instance = super(RateLimiter, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        Initialize the rate limiter (only once for singleton)
        """
        if self._initialized:
            return
        
        # Interval-based rate limiting
        self._last_request_time = 0
        self._rate_limit_seconds = 0
        
        # Time window-based rate limiting
        self._request_times = deque()  # Track timestamps of recent requests
        self._max_requests_per_minute = 20  # Increased limit for better throughput
        self._time_window = 60  # Time window in seconds (1 minute)
        
        self._lock = asyncio.Lock()
        self._initialized = True
    
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
        Async wait if needed before sending the next request
        Enforces both interval-based and time window-based rate limits
        """
        async with self._lock:
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