"""
Authentication Endpoints

速率限制：10 请求/分钟（防止暴力破解）
"""
from fastapi import APIRouter, Request

from langtrader_api.dependencies import APIKey
from langtrader_api.schemas.base import APIResponse
from langtrader_api.middleware.rate_limiter import limiter
from langtrader_api.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/validate", response_model=APIResponse[dict])
@limiter.limit("10/minute")
async def validate_api_key(request: Request, api_key: APIKey):
    """
    Validate API Key
    
    Use this endpoint to verify your API key is valid.
    
    Rate Limit: 10 requests/minute (brute-force protection)
    
    Returns:
        Validation result with key status
    """
    return APIResponse(
        data={
            "valid": True,
            "message": "API Key is valid"
        }
    )


@router.get("/info", response_model=APIResponse[dict])
@limiter.limit("10/minute")
async def auth_info(request: Request, api_key: APIKey):
    """
    Get authentication info
    
    Returns information about the current API key's permissions.
    
    Rate Limit: 10 requests/minute
    """
    return APIResponse(
        data={
            "type": "api_key",
            "permissions": ["read", "write", "execute"],
            "rate_limit": settings.RATE_LIMIT_PER_MINUTE,
        }
    )
