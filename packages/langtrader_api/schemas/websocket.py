"""
WebSocket Message Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from enum import Enum


class WSEventType(str, Enum):
    """WebSocket event types"""
    # Connection events
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    
    # Subscription events
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    
    # Bot events
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    BOT_ERROR = "bot_error"
    CYCLE_STARTED = "cycle_started"
    CYCLE_COMPLETED = "cycle_completed"
    
    # Trading events
    DECISION_MADE = "decision_made"
    TRADE_EXECUTED = "trade_executed"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    
    # Market events
    PRICE_UPDATE = "price_update"
    INDICATOR_UPDATE = "indicator_update"
    
    # System events
    ALERT = "alert"
    PING = "ping"
    PONG = "pong"


class WSMessage(BaseModel):
    """
    WebSocket message format
    
    Example:
        {
            "event": "trade_executed",
            "data": {
                "symbol": "BTC/USDT",
                "action": "open_long",
                "price": 50000.0
            },
            "channel": "bot:1:trades",
            "timestamp": "2024-01-01T00:00:00"
        }
    """
    event: WSEventType
    data: Dict[str, Any] = Field(default_factory=dict)
    channel: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class WSCommand(BaseModel):
    """
    WebSocket command from client
    
    Example:
        {
            "action": "subscribe",
            "channel": "bot:1:trades"
        }
    """
    action: str = Field(..., pattern="^(subscribe|unsubscribe|ping)$")
    channel: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class WSBotUpdate(BaseModel):
    """Bot status update payload"""
    bot_id: int
    status: str  # 'running', 'stopped', 'error'
    cycle: int = 0
    balance: Optional[float] = None
    open_positions: int = 0
    symbols: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class WSTradeUpdate(BaseModel):
    """Trade execution update payload"""
    bot_id: int
    symbol: str
    action: str  # 'open_long', 'close_long', etc.
    price: float
    amount: float
    pnl_usd: Optional[float] = None
    pnl_percent: Optional[float] = None
    order_id: Optional[str] = None


class WSDecisionUpdate(BaseModel):
    """AI decision update payload"""
    bot_id: int
    symbol: str
    action: str
    confidence: float
    reasons: List[str] = Field(default_factory=list)
    quant_score: Optional[float] = None

