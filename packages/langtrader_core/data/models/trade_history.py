# packages/langtrader_core/data/models/trade_history.py
"""
交易历史记录模型
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class TradeHistory(SQLModel, table=True):
    """
    交易历史记录
    记录每笔交易的开平仓信息和盈亏
    """
    __tablename__ = "trade_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bots.id", index=True)
    symbol: str = Field(index=True)
    
    # 交易方向
    side: str  # 'long' / 'short'
    action: str  # 'open_long', 'close_long', 'open_short', 'close_short'
    
    # 价格和数量
    entry_price: Optional[Decimal] = None
    exit_price: Optional[Decimal] = None
    amount: Decimal
    leverage: int = Field(default=1)
    
    # 盈亏
    pnl_usd: Optional[Decimal] = None
    pnl_percent: Optional[Decimal] = None
    fee_paid: Optional[Decimal] = None
    
    # 状态
    status: str = Field(default="open")  # 'open', 'closed'
    
    # 时间
    opened_at: datetime = Field(default_factory=datetime.now)
    closed_at: Optional[datetime] = None
    
    # 关联
    cycle_id: Optional[str] = None
    order_id: Optional[str] = None

