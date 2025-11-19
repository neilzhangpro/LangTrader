import sys
from loguru import logger

logger.remove()

# 控制台输出（带颜色）
logger.add(
    sys.stdout,
    colorize=True,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
)

# 文件输出（按日期分文件，自动轮转）
logger.add(
    "logs/langtrader_{time:YYYY-MM-DD}.log",
    rotation="00:00",  # 每天午夜轮转
    retention="30 days",  # 保留30天
    compression="zip",  # 压缩旧日志
    encoding="utf-8",
    format=(
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{function}:{line} - "
        "{message}"
    )
)

# 错误日志单独记录
logger.add(
    "logs/error_{time:YYYY-MM-DD}.log",
    level="ERROR",
    rotation="100 MB",  # 100MB轮转
    retention="90 days",
    compression="zip",
    encoding="utf-8",
    format=(
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{function}:{line} - "
        "{message}"
    )
)