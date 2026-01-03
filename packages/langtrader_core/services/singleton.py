# packages/langtrader_core/services/singleton.py
"""
单例模式基类

提供线程安全的单例实现，供 Cache、RateLimiter 等服务继承使用。
"""
import threading
from typing import TypeVar, Type

T = TypeVar('T', bound='Singleton')


class Singleton:
    """
    线程安全的单例基类
    
    使用方法：
        class MyService(Singleton):
            def _init_singleton(self):
                # 初始化逻辑（只执行一次）
                self.data = {}
    """
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls: Type[T]) -> T:
        """创建或返回单例实例（双重检查锁定）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """初始化（单例只执行一次）"""
        if self._initialized:
            return
        self._init_singleton()
        self._initialized = True
    
    def _init_singleton(self):
        """子类重写此方法进行初始化"""
        pass
    
    @classmethod
    def reset(cls):
        """重置单例（仅用于测试）"""
        with cls._lock:
            cls._instance = None
            cls._initialized = False

