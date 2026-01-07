# packages/langtrader_api/middleware/rate_limiter.py
"""
速率限制中间件

基于 slowapi 实现，防止 API 滥用和暴力破解。

限制策略：
- 默认：120 请求/分钟（按 API Key）
- 认证端点：10 请求/分钟（防止暴力破解）
- 交易操作：30 请求/分钟（防止过度交易）
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from datetime import datetime
from typing import Callable

from langtrader_api.config import settings


def get_api_key_or_ip(request: Request) -> str:
    """
    获取限流键：优先使用 API Key，否则使用 IP
    
    这样可以：
    1. 同一 API Key 的请求共享配额
    2. 未认证请求按 IP 限制
    """
    # 尝试从 header 获取 API Key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key}"
    
    # 回退到 IP 地址
    return f"ip:{get_remote_address(request)}"


# 创建限流器实例
limiter = Limiter(
    key_func=get_api_key_or_ip,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri=settings.REDIS_URL if settings.REDIS_URL else None,  # 使用 Redis（如可用）
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """
    速率限制超出时的响应处理
    """
    retry_after = exc.detail.split("retry after ")[1] if "retry after" in str(exc.detail) else "60"
    
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": "Rate Limit Exceeded",
            "detail": f"Too many requests. {exc.detail}",
            "code": "RATE_LIMIT_EXCEEDED",
            "timestamp": datetime.now().isoformat(),
            "retry_after": retry_after,
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(settings.RATE_LIMIT_PER_MINUTE),
        }
    )


# =============================================================================
# 预定义的限流装饰器
# =============================================================================

def limit_auth(func: Callable) -> Callable:
    """
    认证端点限流：10 请求/分钟
    用于防止 API Key 暴力破解
    """
    return limiter.limit("10/minute")(func)


def limit_trading(func: Callable) -> Callable:
    """
    交易操作限流：30 请求/分钟
    用于防止过度交易
    """
    return limiter.limit("30/minute")(func)


def limit_heavy(func: Callable) -> Callable:
    """
    重型操作限流：5 请求/分钟
    用于回测等资源密集型操作
    """
    return limiter.limit("5/minute")(func)


def limit_read(func: Callable) -> Callable:
    """
    读取操作限流：200 请求/分钟
    用于只读 API（更宽松）
    """
    return limiter.limit("200/minute")(func)

