"""
Dashboard API Routes

前端 Dashboard 聚合查询 API：
- 系统总览（所有 Bot 状态汇总）
- 单个 Bot 的图表数据
- 全局统计数据
"""
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, List
from datetime import datetime, timedelta
from collections import defaultdict

from langtrader_api.dependencies import APIKey, BotRepo, TradeRepo, PerfService, DbSession
from langtrader_api.schemas.base import APIResponse
from langtrader_api.services.bot_manager import bot_manager
from langtrader_core.data.models.bot import Bot

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# =============================================================================
# System Overview
# =============================================================================

@router.get("/overview", response_model=APIResponse[dict])
async def get_dashboard_overview(
    api_key: APIKey,
    bot_repo: BotRepo,
    trade_repo: TradeRepo,
    db: DbSession,
):
    """
    获取 Dashboard 总览数据
    
    返回：
    - 所有 Bot 的运行状态统计
    - 总 PnL 统计
    - 今日交易统计
    - 活跃 Bot 列表
    """
    # 获取所有 Bot
    all_bots = db.query(Bot).filter(Bot.is_active == True).all()
    
    # 统计 Bot 状态
    total_bots = len(all_bots)
    running_bots = sum(1 for b in all_bots if bot_manager.is_running(b.id))
    
    # 获取今日交易统计
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    all_trades = trade_repo.get_trades(limit=10000)
    today_trades = [t for t in all_trades if t.opened_at >= today_start]
    
    # 计算总 PnL
    closed_trades = [t for t in all_trades if t.status == 'closed' and t.pnl_usd]
    total_pnl = sum(float(t.pnl_usd or 0) for t in closed_trades)
    today_closed = [t for t in today_trades if t.status == 'closed' and t.pnl_usd]
    today_pnl = sum(float(t.pnl_usd or 0) for t in today_closed)
    
    # 计算胜率
    winning_trades = [t for t in closed_trades if float(t.pnl_usd or 0) > 0]
    win_rate = len(winning_trades) / len(closed_trades) * 100 if closed_trades else 0
    
    # 活跃 Bot 列表（正在运行的）
    active_bots = []
    for bot in all_bots:
        if bot_manager.is_running(bot.id):
            process_info = bot_manager.get_process_info(bot.id)
            active_bots.append({
                "id": bot.id,
                "name": bot.name,
                "display_name": bot.display_name,
                "trading_mode": bot.trading_mode,
                "cycle": process_info.get("cycle", 0) if process_info else 0,
                "uptime_seconds": process_info.get("uptime", 0) if process_info else 0,
            })
    
    return APIResponse(
        data={
            "timestamp": datetime.now().isoformat(),
            "bots": {
                "total": total_bots,
                "running": running_bots,
                "stopped": total_bots - running_bots,
            },
            "trades": {
                "total": len(all_trades),
                "today": len(today_trades),
                "open": sum(1 for t in all_trades if t.status == 'open'),
            },
            "performance": {
                "total_pnl_usd": round(total_pnl, 2),
                "today_pnl_usd": round(today_pnl, 2),
                "win_rate": round(win_rate, 1),
                "total_trades_closed": len(closed_trades),
            },
            "active_bots": active_bots,
        }
    )


@router.get("/bots-summary", response_model=APIResponse[list])
async def get_all_bots_summary(
    api_key: APIKey,
    bot_repo: BotRepo,
    trade_repo: TradeRepo,
    perf_service: PerfService,
    db: DbSession,
):
    """
    获取所有 Bot 的摘要信息（用于 Bot 列表页面）
    
    每个 Bot 包含：运行状态、绩效摘要、最近交易
    """
    all_bots = db.query(Bot).filter(Bot.is_active == True).all()
    
    result = []
    for bot in all_bots:
        # 基本信息
        is_running = bot_manager.is_running(bot.id)
        process_info = bot_manager.get_process_info(bot.id) if is_running else None
        
        # 获取绩效
        try:
            metrics = perf_service.calculate_metrics(bot.id, window=50)
            win_rate = metrics.win_rate
            total_pnl = metrics.total_return_usd
            sharpe = metrics.sharpe_ratio
        except Exception:
            win_rate = 0.0
            total_pnl = 0.0
            sharpe = 0.0
        
        # 获取最近交易数量
        recent_trades = trade_repo.get_trades(bot_id=bot.id, limit=10)
        
        result.append({
            "id": bot.id,
            "name": bot.name,
            "display_name": bot.display_name,
            "trading_mode": bot.trading_mode,
            "is_running": is_running,
            "cycle": process_info.get("cycle", 0) if process_info else 0,
            "uptime_seconds": process_info.get("uptime") if process_info else None,
            "performance": {
                "win_rate": round(win_rate, 1),
                "total_pnl_usd": round(total_pnl, 2),
                "sharpe_ratio": round(sharpe, 2),
            },
            "recent_trades_count": len(recent_trades),
            "last_active_at": bot.last_active_at.isoformat() if bot.last_active_at else None,
        })
    
    return APIResponse(data=result)


# =============================================================================
# Bot Charts Data
# =============================================================================

@router.get("/charts/{bot_id}/equity", response_model=APIResponse[list])
async def get_bot_equity_chart(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    trade_repo: TradeRepo,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
):
    """
    获取 Bot 资金曲线数据（用于图表展示）
    
    返回每日的累计 PnL 数据点
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # 获取交易历史
    start_date = datetime.now() - timedelta(days=days)
    trades = trade_repo.get_trades(bot_id=bot_id, limit=10000)
    trades = [t for t in trades if t.opened_at >= start_date and t.status == 'closed']
    
    # 按日期汇总
    daily_pnl = defaultdict(float)
    for trade in trades:
        if trade.pnl_usd:
            date_key = trade.opened_at.date().isoformat()
            daily_pnl[date_key] += float(trade.pnl_usd)
    
    # 生成累计曲线
    result = []
    cumulative = float(bot.initial_balance or 10000)
    
    # 填充日期范围
    current_date = start_date.date()
    end_date = datetime.now().date()
    
    while current_date <= end_date:
        date_str = current_date.isoformat()
        daily_change = daily_pnl.get(date_str, 0)
        cumulative += daily_change
        
        result.append({
            "date": date_str,
            "equity": round(cumulative, 2),
            "daily_pnl": round(daily_change, 2),
        })
        
        current_date += timedelta(days=1)
    
    return APIResponse(data=result)


@router.get("/charts/{bot_id}/trades", response_model=APIResponse[list])
async def get_bot_trades_chart(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    trade_repo: TradeRepo,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
):
    """
    获取 Bot 交易分布数据（用于图表展示）
    
    返回每日交易数量和胜负统计
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # 获取交易历史
    start_date = datetime.now() - timedelta(days=days)
    trades = trade_repo.get_trades(bot_id=bot_id, limit=10000)
    trades = [t for t in trades if t.opened_at >= start_date]
    
    # 按日期汇总
    daily_stats = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl": 0})
    
    for trade in trades:
        date_key = trade.opened_at.date().isoformat()
        daily_stats[date_key]["total"] += 1
        
        if trade.status == 'closed' and trade.pnl_usd:
            pnl = float(trade.pnl_usd)
            daily_stats[date_key]["pnl"] += pnl
            if pnl > 0:
                daily_stats[date_key]["wins"] += 1
            else:
                daily_stats[date_key]["losses"] += 1
    
    # 生成结果
    result = []
    current_date = start_date.date()
    end_date = datetime.now().date()
    
    while current_date <= end_date:
        date_str = current_date.isoformat()
        stats = daily_stats.get(date_str, {"total": 0, "wins": 0, "losses": 0, "pnl": 0})
        
        result.append({
            "date": date_str,
            "trades": stats["total"],
            "wins": stats["wins"],
            "losses": stats["losses"],
            "pnl": round(stats["pnl"], 2),
        })
        
        current_date += timedelta(days=1)
    
    return APIResponse(data=result)


@router.get("/charts/{bot_id}/symbols", response_model=APIResponse[list])
async def get_bot_symbols_distribution(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    trade_repo: TradeRepo,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
):
    """
    获取 Bot 交易币种分布（用于饼图展示）
    
    返回每个币种的交易次数和 PnL
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # 获取交易历史
    start_date = datetime.now() - timedelta(days=days)
    trades = trade_repo.get_trades(bot_id=bot_id, limit=10000)
    trades = [t for t in trades if t.opened_at >= start_date]
    
    # 按币种汇总
    symbol_stats = defaultdict(lambda: {"trades": 0, "pnl": 0, "wins": 0, "losses": 0})
    
    for trade in trades:
        symbol_stats[trade.symbol]["trades"] += 1
        
        if trade.status == 'closed' and trade.pnl_usd:
            pnl = float(trade.pnl_usd)
            symbol_stats[trade.symbol]["pnl"] += pnl
            if pnl > 0:
                symbol_stats[trade.symbol]["wins"] += 1
            else:
                symbol_stats[trade.symbol]["losses"] += 1
    
    # 排序并返回
    result = []
    for symbol, stats in sorted(symbol_stats.items(), key=lambda x: x[1]["trades"], reverse=True):
        total = stats["wins"] + stats["losses"]
        win_rate = stats["wins"] / total * 100 if total > 0 else 0
        
        result.append({
            "symbol": symbol,
            "trades": stats["trades"],
            "pnl": round(stats["pnl"], 2),
            "wins": stats["wins"],
            "losses": stats["losses"],
            "win_rate": round(win_rate, 1),
        })
    
    return APIResponse(data=result)


# =============================================================================
# System Stats
# =============================================================================

@router.get("/stats/global", response_model=APIResponse[dict])
async def get_global_stats(
    api_key: APIKey,
    trade_repo: TradeRepo,
    db: DbSession,
):
    """
    获取全局统计数据
    
    用于系统级别的统计展示
    """
    # 获取所有交易
    all_trades = trade_repo.get_trades(limit=100000)
    closed_trades = [t for t in all_trades if t.status == 'closed']
    
    # 时间范围统计
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    today_trades = [t for t in closed_trades if t.opened_at >= today]
    week_trades = [t for t in closed_trades if t.opened_at >= week_ago]
    month_trades = [t for t in closed_trades if t.opened_at >= month_ago]
    
    def calc_stats(trades):
        if not trades:
            return {"trades": 0, "pnl": 0, "win_rate": 0}
        
        total = len(trades)
        pnl = sum(float(t.pnl_usd or 0) for t in trades)
        wins = sum(1 for t in trades if float(t.pnl_usd or 0) > 0)
        win_rate = wins / total * 100 if total > 0 else 0
        
        return {
            "trades": total,
            "pnl": round(pnl, 2),
            "win_rate": round(win_rate, 1),
        }
    
    # 按 Bot 统计
    bot_stats = defaultdict(lambda: {"trades": 0, "pnl": 0})
    for trade in closed_trades:
        bot_stats[trade.bot_id]["trades"] += 1
        bot_stats[trade.bot_id]["pnl"] += float(trade.pnl_usd or 0)
    
    # 找出表现最好和最差的 Bot
    sorted_bots = sorted(bot_stats.items(), key=lambda x: x[1]["pnl"], reverse=True)
    
    return APIResponse(
        data={
            "all_time": calc_stats(closed_trades),
            "today": calc_stats(today_trades),
            "week": calc_stats(week_trades),
            "month": calc_stats(month_trades),
            "total_open_positions": sum(1 for t in all_trades if t.status == 'open'),
            "bots_count": len(bot_stats),
            "best_bot_id": sorted_bots[0][0] if sorted_bots else None,
            "worst_bot_id": sorted_bots[-1][0] if sorted_bots else None,
        }
    )

