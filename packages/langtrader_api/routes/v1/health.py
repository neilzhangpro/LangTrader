"""
Health Check Endpoints
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, text

from langtrader_api.dependencies import get_db
from langtrader_api.schemas.base import HealthResponse, APIResponse
from langtrader_api.config import settings

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=APIResponse[HealthResponse])
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint (no authentication required)
    
    Returns:
        Health status including database connectivity
    """
    # Check database connection
    db_status = "connected"
    try:
        db.exec(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    health = HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        database=db_status,
    )
    
    return APIResponse(data=health)


@router.get("/ready")
async def readiness_check():
    """
    Kubernetes readiness probe
    """
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """
    Kubernetes liveness probe
    """
    return {"status": "alive"}

