"""
Base API Response Models
"""
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, List, Optional, Any
from datetime import datetime

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper
    
    Example:
        {
            "success": true,
            "data": {...},
            "message": "Operation completed",
            "timestamp": "2024-01-01T00:00:00"
        }
    """
    success: bool = True
    data: T
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated list response
    
    Example:
        {
            "items": [...],
            "total": 100,
            "page": 1,
            "page_size": 20,
            "total_pages": 5
        }
    """
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    
    @classmethod
    def create(
        cls, 
        items: List[T], 
        total: int, 
        page: int, 
        page_size: int
    ) -> "PaginatedResponse[T]":
        """Factory method to create paginated response"""
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )


class ErrorResponse(BaseModel):
    """
    Error response model
    
    Example:
        {
            "success": false,
            "error": "Not Found",
            "detail": "Bot with id 123 not found",
            "code": "BOT_NOT_FOUND",
            "timestamp": "2024-01-01T00:00:00"
        }
    """
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: str
    timestamp: datetime = Field(default_factory=datetime.now)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    version: str
    environment: str
    database: str = "connected"
    timestamp: datetime = Field(default_factory=datetime.now)


class PerformanceMetrics(BaseModel):
    """Performance metrics model"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_return_pct: float = 0.0
    total_return_usd: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0

