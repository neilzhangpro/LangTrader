# packages/langtrader_core/data/repositories/trade_history.py
"""
交易历史仓储
"""
from sqlmodel import select, Session
from langtrader_core.data.models.trade_history import TradeHistory
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from langtrader_core.utils import get_logger

logger = get_logger("trade_history_repository")


class TradeHistoryRepository:
    """交易历史仓储"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(
        self,
        bot_id: int,
        symbol: str,
        side: str,
        action: str,
        amount: float,
        entry_price: Optional[float] = None,
        leverage: int = 1,
        cycle_id: Optional[str] = None,
        order_id: Optional[str] = None,
    ) -> TradeHistory:
        """
        创建新的交易记录（开仓）
        
        Args:
            bot_id: 机器人ID
            symbol: 交易对
            side: 方向 ('long' / 'short')
            action: 动作 ('open_long', 'open_short')
            amount: 数量
            entry_price: 入场价格
            leverage: 杠杆
            cycle_id: 周期ID
            order_id: 订单ID
        """
        trade = TradeHistory(
            bot_id=bot_id,
            symbol=symbol,
            side=side,
            action=action,
            amount=Decimal(str(amount)),
            entry_price=Decimal(str(entry_price)) if entry_price else None,
            leverage=leverage,
            status="open",
            opened_at=datetime.now(),
            cycle_id=cycle_id,
            order_id=order_id,
        )
        self.session.add(trade)
        self.session.commit()
        self.session.refresh(trade)
        logger.info(f"✅ Created trade: {symbol} {side} @ {entry_price}")
        return trade
    
    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        pnl_usd: float,
        pnl_percent: float,
        fee_paid: Optional[float] = None,
    ) -> Optional[TradeHistory]:
        """
        关闭交易（平仓）
        
        Args:
            trade_id: 交易ID
            exit_price: 出场价格
            pnl_usd: 盈亏金额 (USD)
            pnl_percent: 盈亏百分比
            fee_paid: 手续费
        """
        trade = self.get_by_id(trade_id)
        if not trade:
            logger.warning(f"Trade {trade_id} not found")
            return None
        
        trade.exit_price = Decimal(str(exit_price))
        trade.pnl_usd = Decimal(str(pnl_usd))
        trade.pnl_percent = Decimal(str(pnl_percent))
        trade.fee_paid = Decimal(str(fee_paid)) if fee_paid else None
        trade.status = "closed"
        trade.closed_at = datetime.now()
        
        self.session.add(trade)
        self.session.commit()
        self.session.refresh(trade)
        
        logger.info(f"✅ Closed trade: {trade.symbol} PnL: ${pnl_usd:.2f} ({pnl_percent:.2f}%)")
        return trade
    
    def close_trade_by_symbol(
        self,
        bot_id: int,
        symbol: str,
        exit_price: float,
        pnl_usd: float,
        pnl_percent: float,
        fee_paid: Optional[float] = None,
    ) -> Optional[TradeHistory]:
        """
        通过 symbol 关闭最近的开仓交易
        """
        # 查找最近的开仓交易
        statement = (
            select(TradeHistory)
            .where(TradeHistory.bot_id == bot_id)
            .where(TradeHistory.symbol == symbol)
            .where(TradeHistory.status == "open")
            .order_by(TradeHistory.opened_at.desc())
        )
        trade = self.session.exec(statement).first()
        
        if not trade:
            logger.warning(f"No open trade found for {symbol}")
            return None
        
        return self.close_trade(
            trade_id=trade.id,
            exit_price=exit_price,
            pnl_usd=pnl_usd,
            pnl_percent=pnl_percent,
            fee_paid=fee_paid,
        )
    
    def get_by_id(self, trade_id: int) -> Optional[TradeHistory]:
        """通过ID获取交易"""
        statement = select(TradeHistory).where(TradeHistory.id == trade_id)
        return self.session.exec(statement).first()
    
    def get_by_bot(
        self, 
        bot_id: int, 
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[TradeHistory]:
        """
        获取机器人的交易历史
        
        Args:
            bot_id: 机器人ID
            status: 状态过滤 ('open', 'closed', None=全部)
            limit: 返回数量限制
        """
        statement = select(TradeHistory).where(TradeHistory.bot_id == bot_id)
        
        if status:
            statement = statement.where(TradeHistory.status == status)
        
        statement = statement.order_by(TradeHistory.opened_at.desc()).limit(limit)
        
        return list(self.session.exec(statement).all())
    
    def get_closed_trades(
        self, 
        bot_id: int, 
        limit: int = 50
    ) -> List[TradeHistory]:
        """
        获取已平仓的交易（用于绩效计算）
        
        Args:
            bot_id: 机器人ID
            limit: 返回数量限制（最近 N 笔）
        """
        return self.get_by_bot(bot_id, status="closed", limit=limit)
    
    def get_open_trades(self, bot_id: int) -> List[TradeHistory]:
        """获取所有未平仓交易"""
        return self.get_by_bot(bot_id, status="open", limit=100)
    
    def get_open_trade_by_symbol(
        self, 
        bot_id: int, 
        symbol: str
    ) -> Optional[TradeHistory]:
        """获取指定 symbol 的开仓交易"""
        statement = (
            select(TradeHistory)
            .where(TradeHistory.bot_id == bot_id)
            .where(TradeHistory.symbol == symbol)
            .where(TradeHistory.status == "open")
            .order_by(TradeHistory.opened_at.desc())
        )
        return self.session.exec(statement).first()
    
    def get_recent_trades(
        self, 
        bot_id: int, 
        limit: int = 10
    ) -> List[TradeHistory]:
        """
        获取最近的已平仓交易（用于计算连续亏损等）
        
        Args:
            bot_id: 机器人ID
            limit: 返回数量限制（默认最近 10 笔）
        
        Returns:
            按关闭时间降序排列的已平仓交易列表
        """
        statement = (
            select(TradeHistory)
            .where(TradeHistory.bot_id == bot_id)
            .where(TradeHistory.status == "closed")
            .order_by(TradeHistory.closed_at.desc())
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

