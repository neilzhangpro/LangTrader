"""
API Schemas - Pydantic models for request/response
"""
from langtrader_api.schemas.base import (
    APIResponse,
    PaginatedResponse,
    ErrorResponse,
)
from langtrader_api.schemas.bots import (
    BotSummary,
    BotDetail,
    BotStatus,
    BotCreateRequest,
    BotUpdateRequest,
)
from langtrader_api.schemas.trades import (
    TradeRecord,
    TradeSummary,
    DailyPerformance,
)
from langtrader_api.schemas.websocket import (
    WSMessage,
    WSEventType,
    WSCommand,
)

__all__ = [
    # Base
    "APIResponse",
    "PaginatedResponse",
    "ErrorResponse",
    # Bots
    "BotSummary",
    "BotDetail",
    "BotStatus",
    "BotCreateRequest",
    "BotUpdateRequest",
    # Trades
    "TradeRecord",
    "TradeSummary",
    "DailyPerformance",
    # WebSocket
    "WSMessage",
    "WSEventType",
    "WSCommand",
]

