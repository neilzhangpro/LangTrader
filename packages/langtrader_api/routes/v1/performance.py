"""
Performance Metrics API Routes
"""
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional

from langtrader_api.dependencies import APIKey, BotRepo, PerfService
from langtrader_api.schemas.base import APIResponse, PerformanceMetrics

router = APIRouter(prefix="/performance", tags=["Performance"])


@router.get("/{bot_id}", response_model=APIResponse[PerformanceMetrics])
async def get_bot_performance(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    perf_service: PerfService,
    window: int = Query(50, ge=1, le=500, description="Number of trades to analyze"),
):
    """
    Get performance metrics for a bot
    
    Calculates:
    - Win rate
    - Sharpe ratio
    - Max drawdown
    - Profit factor
    - Average returns
    """
    # Verify bot exists
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # Calculate metrics
    try:
        metrics = perf_service.calculate_metrics(bot_id, window=window)
        
        return APIResponse(
            data=PerformanceMetrics(
                total_trades=metrics.total_trades,
                winning_trades=metrics.winning_trades,
                losing_trades=metrics.losing_trades,
                win_rate=metrics.win_rate,
                avg_return_pct=metrics.avg_return_pct,
                total_return_usd=metrics.total_return_usd,
                sharpe_ratio=metrics.sharpe_ratio,
                max_drawdown=metrics.max_drawdown,
                profit_factor=metrics.profit_factor,
                avg_win_pct=metrics.avg_win_pct,
                avg_loss_pct=metrics.avg_loss_pct,
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate performance: {str(e)}"
        )


@router.get("/{bot_id}/recent", response_model=APIResponse[dict])
async def get_recent_trades_summary(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    perf_service: PerfService,
    limit: int = Query(10, ge=1, le=50, description="Number of recent trades"),
):
    """
    Get summary of recent trades (for dashboard display)
    """
    # Verify bot exists
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    try:
        summary_text = perf_service.get_recent_trades_summary(bot_id, limit=limit)
        
        return APIResponse(
            data={
                "bot_id": bot_id,
                "limit": limit,
                "summary": summary_text
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent trades: {str(e)}"
        )


@router.get("/compare", response_model=APIResponse[dict])
async def compare_bots_performance(
    api_key: APIKey,
    bot_repo: BotRepo,
    perf_service: PerfService,
    bot_ids: str = Query(..., description="Comma-separated bot IDs"),
    window: int = Query(50, ge=1, le=500),
):
    """
    Compare performance metrics across multiple bots
    """
    ids = [int(id.strip()) for id in bot_ids.split(",") if id.strip()]
    
    if len(ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 bot IDs required for comparison"
        )
    
    results = {}
    for bot_id in ids:
        bot = bot_repo.get_by_id(bot_id)
        if not bot:
            results[bot_id] = {"error": "Bot not found"}
            continue
        
        try:
            metrics = perf_service.calculate_metrics(bot_id, window=window)
            results[bot_id] = {
                "name": bot.name,
                "win_rate": metrics.win_rate,
                "sharpe_ratio": metrics.sharpe_ratio,
                "total_return_usd": metrics.total_return_usd,
                "total_trades": metrics.total_trades,
                "max_drawdown": metrics.max_drawdown,
            }
        except Exception as e:
            results[bot_id] = {"error": str(e)}
    
    return APIResponse(data={"bots": results, "window": window})

