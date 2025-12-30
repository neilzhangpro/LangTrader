# packages/langtrader_core/utils/logger.py
import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from logging.handlers import RotatingFileHandler

# 尝试使用 rich 库增强日志显示（可选）
try:
    from rich.logging import RichHandler
    from rich.console import Console
    from rich.traceback import install
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器"""
    
    # ANSI 颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 添加颜色
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


class TradingLogger:
    """交易系统统一日志管理器"""
    
    _instance: Optional['TradingLogger'] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.logger = logging.getLogger('langtrader')
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重复添加 handler
        if self.logger.handlers:
            return
        
        self._setup_handlers()
        self._initialized = True
    
    def _setup_handlers(self):
        """配置日志处理器"""
        # 控制台处理器
        if RICH_AVAILABLE:
            console_handler = RichHandler(
                console=Console(stderr=True),
                show_time=True,
                show_path=True,
                rich_tracebacks=True,
                markup=True,
            )
            console_handler.setLevel(logging.INFO)
        else:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            formatter = ColoredFormatter(
                # 添加文件名和行号信息
                fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
        
        # 文件处理器（带轮转）
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_dir / 'langtrader.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        
        # 错误日志单独文件
        error_handler = RotatingFileHandler(
            log_dir / 'langtrader_error.log',
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        # 添加处理器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
    
    def get_logger(self, name: Optional[str] = None):
        """获取日志记录器"""
        if name:
            return self.logger.getChild(name)
        return self.logger
    
    def set_context(self, **kwargs):
        """设置日志上下文（如 trade_id, cycle_id 等）"""
        for key, value in kwargs.items():
            setattr(self.logger, key, value)
    
    def clear_context(self):
        """清除日志上下文"""
        # 可以在这里清除自定义属性


# 便捷函数
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取日志记录器的便捷函数"""
    trading_logger = TradingLogger()
    return trading_logger.get_logger(name)


# 带上下文的日志装饰器
class LogContext:
    """日志上下文管理器"""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
        self.old_filters = []
    
    def __enter__(self):
        class ContextFilter(logging.Filter):
            def __init__(self, context):
                super().__init__()
                self.context = context
            
            def filter(self, record):
                for key, value in self.context.items():
                    setattr(record, key, value)
                return True
        
        filter_obj = ContextFilter(self.context)
        self.logger.addFilter(filter_obj)
        self.old_filters.append(filter_obj)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        for filter_obj in self.old_filters:
            self.logger.removeFilter(filter_obj)


# 使用示例和导出
__all__ = ['get_logger', 'TradingLogger', 'LogContext']