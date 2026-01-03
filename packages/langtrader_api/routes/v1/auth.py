"""
Authentication Endpoints
"""
from fastapi import APIRouter

from langtrader_api.dependencies import APIKey
from langtrader_api.schemas.base import APIResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/validate", response_model=APIResponse[dict])
async def validate_api_key(api_key: APIKey):
    """
    Validate API Key
    
    Use this endpoint to verify your API key is valid.
    
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
async def auth_info(api_key: APIKey):
    """
    Get authentication info
    
    Returns information about the current API key's permissions.
    """
    return APIResponse(
        data={
            "type": "api_key",
            "permissions": ["read", "write", "execute"],
            "rate_limit": 120,  # requests per minute
        }
    )

