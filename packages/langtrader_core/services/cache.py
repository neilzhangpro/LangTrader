"""
A cache system for the trading system (Singleton pattern).
All services share the same cache instance for better efficiency.
"""
from dataclasses import dataclass
from langtrader_core.utils import get_logger
logger = get_logger("cache")
from typing import Any, Optional
import threading
import time

@dataclass
class CacheItem:
    """
    A cache item containing data, timestamp, and TTL
    """
    data: Any
    timestamp: float
    ttl: float

class Cache:
    """
    A cache system for the trading system (Singleton pattern)
    Ensures all services share the same cache to avoid redundant API calls
    """
    _instance = None  # Class instance to store the singleton instance
    _lock = threading.Lock()  # Lock for thread-safe singleton creation

    def __new__(cls):
        """
        Create or return the singleton instance
        Uses double-checked locking for thread safety
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(Cache, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        Initialize the cache (only once for singleton)
        """
        if self._initialized:
            return
        
        self.cache = {}
        self._cache_lock = threading.Lock()  # Instance-level lock for cache operations

        # Different cache TTL for different data types (in seconds)
        self.cache_ttl = {
            'tickers': 10,            # 10 seconds (更快的行情更新)
            'ohlcv_3m': 300,          # 5 minutes (增加软过期，防止 WebSocket 挂掉后读取陈旧数据)
            'ohlcv_4h': 3600,         # 1 hour (REST API，更及时的趋势判断)
            'ohlcv': 600,             # 10 minutes (default for OHLCV)
            'open_interests': 600,    # 10 minutes (更快的热度跟踪)
            'markets': 3600,          # 1 hour (市场信息)
            'coin_selection': 600,    # 10 minutes (更频繁地调整选币)
            'backtest_ohlcv': 86400 * 7,  # 7天（回测数据长期缓存）
        }
        
        self._initialized = True
        logger.info("Cache singleton instance initialized")

    
    def _make_key(self, data_type: str, *args, **kwargs) -> str:
        """
        Make a unique key for the cache entry
        
        Args:
            data_type: Type of data being cached
            args: Positional arguments to include in key
            kwargs: Keyword arguments to include in key
            
        Returns:
            A unique string key for this cache entry
        """
        args_str = '_'.join(str(arg) for arg in args)
        kwargs_str = '_'.join(f'{k}={v}' for k, v in kwargs.items())
        return f'{data_type}:{args_str}:{kwargs_str}'
    
    def get(self, data_type: str, *args, **kwargs) -> Any:
        """
        Get a value from the cache
        
        Args:
            data_type: Type of data to retrieve
            args: Positional arguments used to create the key
            kwargs: Keyword arguments used to create the key
            
        Returns:
            The cached data if found and not expired, None otherwise
        """
        key = self._make_key(data_type, *args, **kwargs)
        with self._cache_lock:
            entry = self.cache.get(key)
            if entry is None:
                return None
            
            # Check if the cache is expired
            ttl = self.cache_ttl.get(data_type, 0)
            if ttl > 0 and time.time() - entry.timestamp > ttl:
                # Cache expired, delete and return None
                del self.cache[key]
                logger.debug(f"Cache expired for key: {key}")
                return None
            
            logger.debug(f"Cache hit for key: {key}")
            return entry.data
    
    def set(self, data_type: str, data: Any, *args, **kwargs):
        """
        Set a value in the cache
        
        Args:
            data_type: Type of data being cached
            data: The data to cache
            args: Positional arguments used to create the key
            kwargs: Keyword arguments used to create the key
        """
        key = self._make_key(data_type, *args, **kwargs)
        with self._cache_lock:
            self.cache[key] = CacheItem(data, time.time(), self.cache_ttl.get(data_type, 0))
            logger.debug(f"Cache set for key: {key}")
    
    def delete(self, data_type: str, *args, **kwargs):
        """
        Delete a specific cache entry
        
        Args:
            data_type: Type of data to delete
            args: Positional arguments used to create the key
            kwargs: Keyword arguments used to create the key
        """
        key = self._make_key(data_type, *args, **kwargs)
        with self._cache_lock:
            if key in self.cache:
                del self.cache[key]
                logger.debug(f"Deleted cache entry: {key}")
                return True
            return False
    
    def get_entry_age(self, data_type: str, *args, **kwargs) -> Optional[float]:
        """
        Get the age of a cache entry in seconds
        
        Args:
            data_type: Type of data
            args: Positional arguments used to create the key
            kwargs: Keyword arguments used to create the key
            
        Returns:
            Age in seconds if entry exists, None otherwise
        """
        key = self._make_key(data_type, *args, **kwargs)
        with self._cache_lock:
            entry = self.cache.get(key)
            if entry is None:
                return None
            return time.time() - entry.timestamp
    
    def clear(self, data_type: Optional[str] = None):
        """
        Clear the cache
        
        Args:
            data_type: If provided, only clear entries of this type. If None, clear all.
        """
        with self._cache_lock:
            if data_type is None:
                count = len(self.cache)
                self.cache.clear()
                logger.info(f"Cleared all cache entries ({count} items)")
            else:
                # Clear the cache for the specific data type
                keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{data_type}:")]
                for key in keys_to_delete:
                    del self.cache[key]
                logger.info(f"Cleared {len(keys_to_delete)} cache entries for type: {data_type}")

    def get_stats(self) -> dict:
        """
        Get statistics about the cache
        
        Returns:
            Dictionary containing cache statistics
        """
        with self._cache_lock:
            return {
                'total_items': len(self.cache),
                'by_type': self._count_by_type(),
                'memory_usage': self._estimate_memory_usage()
            }
    
    def _count_by_type(self) -> dict:
        """
        Count the cached items by data type
        
        Returns:
            Dictionary mapping data types to item counts
        """
        counts = {}
        for key in self.cache.keys():
            data_type = key.split(':')[0]
            counts[data_type] = counts.get(data_type, 0) + 1
        return counts

    def _estimate_memory_usage(self) -> int:
        """
        Estimate the memory usage of the cache
        
        Returns:
            Approximate memory usage in bytes
        """
        import sys
        return sum(sys.getsizeof(v.data) for v in self.cache.values())