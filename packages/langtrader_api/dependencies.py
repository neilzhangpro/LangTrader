"""
Dependency Injection for FastAPI
Integrates with langtrader_core services
"""
from typing import Annotated, Generator
from fastapi import Depends, HTTPException, Header, status
from sqlmodel import Session

from langtrader_core.data import SessionLocal, init_db
from langtrader_core.data.repositories.bot import BotRepository
from langtrader_core.data.repositories.trade_history import TradeHistoryRepository
from langtrader_core.data.repositories.workflow import WorkflowRepository
from langtrader_core.data.repositories.exchange import ExchangeRepository
from langtrader_core.data.repositories.llm_config import LLMConfigRepository
from langtrader_core.services.performance import PerformanceService
from langtrader_api.config import settings


# =============================================================================
# Database Session
# =============================================================================

def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# API Key Authentication
# =============================================================================

async def validate_api_key(
    x_api_key: str = Header(..., description="API Key for authentication")
) -> str:
    """
    Validate API Key from header
    
    Usage:
        @router.get("/protected")
        async def protected_route(api_key: APIKey):
            ...
    """
    if x_api_key not in settings.API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


# =============================================================================
# Repository Dependencies
# =============================================================================

def get_bot_repository(
    db: Annotated[Session, Depends(get_db)]
) -> BotRepository:
    """Get BotRepository instance"""
    return BotRepository(db)


def get_trade_history_repository(
    db: Annotated[Session, Depends(get_db)]
) -> TradeHistoryRepository:
    """Get TradeHistoryRepository instance"""
    return TradeHistoryRepository(db)


def get_workflow_repository(
    db: Annotated[Session, Depends(get_db)]
) -> WorkflowRepository:
    """Get WorkflowRepository instance"""
    return WorkflowRepository(db)


def get_exchange_repository(
    db: Annotated[Session, Depends(get_db)]
) -> ExchangeRepository:
    """Get ExchangeRepository instance"""
    return ExchangeRepository(db)


def get_llm_config_repository(
    db: Annotated[Session, Depends(get_db)]
) -> LLMConfigRepository:
    """Get LLMConfigRepository instance"""
    return LLMConfigRepository(db)


def get_performance_service(
    db: Annotated[Session, Depends(get_db)]
) -> PerformanceService:
    """Get PerformanceService instance"""
    return PerformanceService(db)


# =============================================================================
# Type Aliases for Clean Route Signatures
# =============================================================================

DbSession = Annotated[Session, Depends(get_db)]
APIKey = Annotated[str, Depends(validate_api_key)]
BotRepo = Annotated[BotRepository, Depends(get_bot_repository)]
TradeRepo = Annotated[TradeHistoryRepository, Depends(get_trade_history_repository)]
WorkflowRepo = Annotated[WorkflowRepository, Depends(get_workflow_repository)]
ExchangeRepo = Annotated[ExchangeRepository, Depends(get_exchange_repository)]
LLMConfigRepo = Annotated[LLMConfigRepository, Depends(get_llm_config_repository)]
PerfService = Annotated[PerformanceService, Depends(get_performance_service)]


# =============================================================================
# Startup/Shutdown Hooks
# =============================================================================

async def init_services():
    """Initialize services on application startup"""
    init_db()


async def shutdown_services():
    """Cleanup services on application shutdown"""
    pass

