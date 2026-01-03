"""
Trade History API Routes
"""
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime, timedelta

from langtrader_api.dependencies import APIKey, TradeRepo
from langtrader_api.schemas.base import APIResponse, PaginatedResponse
from langtrader_api.schemas.trades import TradeRecord, TradeSummary, DailyPerformance

router = APIRouter(prefix="/trades", tags=["Trades"])


@router.get("", response_model=APIResponse[PaginatedResponse[TradeRecord]])
async def list_trades(
    api_key: APIKey,
    trade_repo: TradeRepo,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    bot_id: Optional[int] = Query(None, description="Filter by bot ID"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    status: Optional[str] = Query(None, description="Filter by status (open/closed)"),
    side: Optional[str] = Query(None, description="Filter by side (long/short)"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
):
    """
    List trade history with filters
    """
    # Get trades using repository
    trades = trade_repo.get_trades(
        bot_id=bot_id,
        symbol=symbol,
        limit=page_size * 10  # Get more for filtering
    )
    
    # Apply additional filters
    filtered = trades
    if status:
        filtered = [t for t in filtered if t.status == status]
    if side:
        filtered = [t for t in filtered if t.side == side]
    if start_date:
        filtered = [t for t in filtered if t.opened_at >= start_date]
    if end_date:
        filtered = [t for t in filtered if t.opened_at <= end_date]
    
    total = len(filtered)
    
    # Paginate
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    items = filtered[start_idx:end_idx]
    
    return APIResponse(
        data=PaginatedResponse.create(
            items=[TradeRecord.model_validate(t) for t in items],
            total=total,
            page=page,
            page_size=page_size
        )
    )


@router.get("/summary", response_model=APIResponse[TradeSummary])
async def get_trade_summary(
    api_key: APIKey,
    trade_repo: TradeRepo,
    bot_id: int = Query(..., description="Bot ID"),
    period: str = Query("all", description="Period: day, week, month, all"),
):
    """
    Get trade summary for a period
    """
    # Calculate date range
    now = datetime.now()
    if period == "day":
        start_date = now - timedelta(days=1)
    elif period == "week":
        start_date = now - timedelta(weeks=1)
    elif period == "month":
        start_date = now - timedelta(days=30)
    else:
        start_date = None
    
    # Get trades
    trades = trade_repo.get_trades(bot_id=bot_id, limit=1000)
    
    # Filter by date
    if start_date:
        trades = [t for t in trades if t.opened_at >= start_date]
    
    # Calculate summary
    total_trades = len(trades)
    closed_trades = [t for t in trades if t.status == "closed"]
    open_trades = [t for t in trades if t.status == "open"]
    
    winning = [t for t in closed_trades if t.pnl_usd and float(t.pnl_usd) > 0]
    losing = [t for t in closed_trades if t.pnl_usd and float(t.pnl_usd) < 0]
    
    total_pnl = sum(float(t.pnl_usd or 0) for t in closed_trades)
    total_fees = sum(float(t.fee_paid or 0) for t in trades)
    
    pnl_values = [float(t.pnl_usd) for t in closed_trades if t.pnl_usd]
    
    summary = TradeSummary(
        bot_id=bot_id,
        period=period,
        total_trades=total_trades,
        winning_trades=len(winning),
        losing_trades=len(losing),
        open_trades=len(open_trades),
        total_pnl_usd=total_pnl,
        total_fees_usd=total_fees,
        net_pnl_usd=total_pnl - total_fees,
        best_trade_pnl=max(pnl_values) if pnl_values else 0,
        worst_trade_pnl=min(pnl_values) if pnl_values else 0,
        avg_trade_pnl=sum(pnl_values) / len(pnl_values) if pnl_values else 0,
        symbols_traded=list(set(t.symbol for t in trades)),
    )
    
    return APIResponse(data=summary)


@router.get("/daily", response_model=APIResponse[List[DailyPerformance]])
async def get_daily_performance(
    api_key: APIKey,
    trade_repo: TradeRepo,
    bot_id: int = Query(..., description="Bot ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days"),
):
    """
    Get daily performance breakdown
    """
    from collections import defaultdict
    
    # Get trades for the period
    start_date = datetime.now() - timedelta(days=days)
    trades = trade_repo.get_trades(bot_id=bot_id, limit=10000)
    trades = [t for t in trades if t.opened_at >= start_date]
    
    # Group by date
    daily_data = defaultdict(lambda: {
        "trades": 0,
        "winning": 0,
        "losing": 0,
        "pnl_usd": 0.0,
        "fees_usd": 0.0,
        "symbols": set()
    })
    
    for trade in trades:
        date_key = trade.opened_at.date()
        daily_data[date_key]["trades"] += 1
        daily_data[date_key]["symbols"].add(trade.symbol)
        daily_data[date_key]["fees_usd"] += float(trade.fee_paid or 0)
        
        if trade.status == "closed" and trade.pnl_usd:
            pnl = float(trade.pnl_usd)
            daily_data[date_key]["pnl_usd"] += pnl
            if pnl > 0:
                daily_data[date_key]["winning"] += 1
            else:
                daily_data[date_key]["losing"] += 1
    
    # Convert to response format
    result = []
    for date_key, data in sorted(daily_data.items()):
        result.append(DailyPerformance(
            date=date_key,
            bot_id=bot_id,
            trades=data["trades"],
            winning_trades=data["winning"],
            losing_trades=data["losing"],
            pnl_usd=data["pnl_usd"],
            pnl_percent=0.0,  # Would need balance history to calculate
            fees_usd=data["fees_usd"],
            symbols=list(data["symbols"]),
        ))
    
    return APIResponse(data=result)


@router.get("/{trade_id}", response_model=APIResponse[TradeRecord])
async def get_trade(
    trade_id: int,
    api_key: APIKey,
    trade_repo: TradeRepo,
):
    """
    Get trade details by ID
    """
    trade = trade_repo.get_by_id(trade_id)
    if not trade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trade with id {trade_id} not found"
        )
    return APIResponse(data=TradeRecord.model_validate(trade))

