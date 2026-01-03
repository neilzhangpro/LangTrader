"""
Trade-related API Schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal


class TradeRecord(BaseModel):
    """Trade history record"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    bot_id: int
    symbol: str
    side: str  # 'long' / 'short'
    action: str  # 'open_long', 'close_long', etc.
    
    # Prices
    entry_price: Optional[Decimal] = None
    exit_price: Optional[Decimal] = None
    amount: Decimal
    leverage: int = 1
    
    # P&L
    pnl_usd: Optional[Decimal] = None
    pnl_percent: Optional[Decimal] = None
    fee_paid: Optional[Decimal] = None
    
    # Status
    status: str  # 'open', 'closed'
    
    # Timestamps
    opened_at: datetime
    closed_at: Optional[datetime] = None
    
    # References
    cycle_id: Optional[str] = None
    order_id: Optional[str] = None


class TradeSummary(BaseModel):
    """Trade summary for a period"""
    bot_id: int
    period: str  # 'day', 'week', 'month', 'all'
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    open_trades: int = 0
    
    total_pnl_usd: float = 0.0
    total_fees_usd: float = 0.0
    net_pnl_usd: float = 0.0
    
    best_trade_pnl: float = 0.0
    worst_trade_pnl: float = 0.0
    avg_trade_pnl: float = 0.0
    
    symbols_traded: List[str] = Field(default_factory=list)


class DailyPerformance(BaseModel):
    """Daily performance summary"""
    date: date
    bot_id: int
    
    trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    pnl_usd: float = 0.0
    pnl_percent: float = 0.0
    fees_usd: float = 0.0
    
    symbols: List[str] = Field(default_factory=list)


class TradeFilter(BaseModel):
    """Trade query filters"""
    bot_id: Optional[int] = None
    symbol: Optional[str] = None
    side: Optional[str] = Field(None, pattern="^(long|short)$")
    status: Optional[str] = Field(None, pattern="^(open|closed)$")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class BacktestRequest(BaseModel):
    """Backtest request parameters"""
    bot_id: int
    start_date: datetime
    end_date: datetime
    initial_balance: float = Field(default=10000.0, ge=100)
    symbols: Optional[List[str]] = Field(
        None,
        description="Specific symbols to backtest (default: auto-select)"
    )
    max_cycles: Optional[int] = Field(
        None,
        ge=1,
        description="Limit number of cycles (for quick testing)"
    )


class BacktestResult(BaseModel):
    """Backtest result summary"""
    task_id: str
    bot_id: int
    status: str  # 'pending', 'running', 'completed', 'failed'
    progress: float = 0.0  # 0-100
    
    # Results (populated when completed)
    total_return: Optional[float] = None
    return_pct: Optional[float] = None
    final_balance: Optional[float] = None
    total_trades: Optional[int] = None
    win_rate: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    profit_factor: Optional[float] = None
    
    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    # Error info
    error: Optional[str] = None

