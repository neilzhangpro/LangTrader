"""
缓存服务（单例模式）

为交易系统提供统一的缓存机制，避免重复 API 调用。
"""
from dataclasses import dataclass
from typing import Any, Optional
import threading
import time

from langtrader_core.services.singleton import Singleton
from langtrader_core.utils import get_logger

logger = get_logger("cache")


@dataclass
class CacheItem:
    """缓存条目"""
    data: Any
    timestamp: float
    ttl: float


class Cache(Singleton):
    """
    缓存服务（单例模式）
    继承 Singleton 基类实现线程安全的单例
    """
    
    def _init_singleton(self):
        """初始化缓存"""
        self.cache = {}
        self._cache_lock = threading.Lock()
        self.cache_ttl = self._get_default_ttls()
        logger.info("Cache singleton initialized")
    
    @staticmethod
    def _get_default_ttls() -> dict:
        """获取默认TTL配置（向后兼容）"""
        return {
            'tickers': 30,            # 30 seconds (与选币到执行的时间间隔匹配)
            'ohlcv_3m': 300,          # 5 minutes
            'ohlcv_4h': 3600,         # 1 hour
            'ohlcv': 600,             # 10 minutes
            'open_interests': 600,    # 10 minutes
            'markets': 3600,          # 1 hour
            'coin_selection': 600,    # 10 minutes
            'backtest_ohlcv': 86400 * 7,  # 7 days
            'orderbook': 60,          # 60 seconds
            'trades': 60,             # 60 seconds
        }

    
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
    
    def set_cycle_interval(self, interval_seconds: int):
        """
        根据循环间隔动态调整缓存 TTL
        
        策略：选币缓存 TTL = cycle_interval * 0.9（略短于循环间隔）
        确保每轮开始时选币缓存已过期，触发重新选币。
        
        Args:
            interval_seconds: 交易周期间隔（秒）
        """
        # coin_selection 缓存应该在每轮开始前过期
        new_ttl = max(60, int(interval_seconds * 0.9))
        self.cache_ttl['coin_selection'] = new_ttl
        logger.info(f"Cache TTL adjusted: coin_selection={new_ttl}s (cycle_interval={interval_seconds}s)")
    
    def invalidate(self, data_type: str, *args, **kwargs):
        """
        使指定类型的缓存失效
        
        Args:
            data_type: 缓存类型（如 'coin_selection'）
            args/kwargs: 可选，用于构建具体的 key
        """
        with self._cache_lock:
            if args or kwargs:
                # 删除特定 key
                key = self._make_key(data_type, *args, **kwargs)
                if key in self.cache:
                    del self.cache[key]
                    logger.debug(f"Cache invalidated: {key}")
            else:
                # 删除该类型的所有缓存
                keys_to_delete = [k for k in self.cache.keys() if k.startswith(f"{data_type}:")]
                for key in keys_to_delete:
                    del self.cache[key]
                if keys_to_delete:
                    logger.debug(f"Cache invalidated: {len(keys_to_delete)} entries of type '{data_type}'")
    
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

    def cleanup_expired(self) -> int:
        """
        主动清理过期缓存条目
        
        遍历所有缓存条目，删除已过期的条目。
        建议在每个交易周期开始时调用，防止内存无限增长。
        
        Returns:
            清理的条目数量
        """
        with self._cache_lock:
            now = time.time()
            keys_to_delete = []
            
            for key, entry in self.cache.items():
                # 从 key 中提取 data_type
                data_type = key.split(':')[0]
                ttl = self.cache_ttl.get(data_type, 0)
                
                # 检查是否过期
                if ttl > 0 and now - entry.timestamp > ttl:
                    keys_to_delete.append(key)
            
            # 删除过期条目
            for key in keys_to_delete:
                del self.cache[key]
            
            if keys_to_delete:
                logger.debug(f"🧹 Cleaned up {len(keys_to_delete)} expired cache entries")
            
            return len(keys_to_delete)

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