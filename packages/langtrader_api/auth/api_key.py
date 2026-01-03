"""
API Key Authentication
Simple header-based authentication for internal/single-user usage
"""
from fastapi import HTTPException, Header, status
from langtrader_api.config import settings


async def validate_api_key(
    x_api_key: str = Header(
        ..., 
        alias="X-API-Key",
        description="API Key for authentication"
    )
) -> str:
    """
    Validate API Key from X-API-Key header
    
    Returns:
        The validated API key
        
    Raises:
        HTTPException: If API key is invalid
    """
    if x_api_key not in settings.API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


async def validate_api_key_optional(
    x_api_key: str = Header(
        None, 
        alias="X-API-Key",
        description="Optional API Key"
    )
) -> str | None:
    """
    Optional API Key validation
    Returns None if no key provided, raises exception if invalid key
    """
    if x_api_key is None:
        return None
    
    if x_api_key not in settings.API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key

