"""
Backtest API Routes
"""
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import Dict, Optional
from datetime import datetime
from uuid import uuid4

from langtrader_api.dependencies import APIKey, BotRepo, DbSession
from langtrader_api.schemas.base import APIResponse
from langtrader_api.schemas.trades import BacktestRequest, BacktestResult

router = APIRouter(prefix="/backtests", tags=["Backtests"])

# In-memory storage for backtest results (use Redis in production)
_backtest_results: Dict[str, BacktestResult] = {}


@router.post("", response_model=APIResponse[BacktestResult], status_code=status.HTTP_202_ACCEPTED)
async def start_backtest(
    request: BacktestRequest,
    api_key: APIKey,
    bot_repo: BotRepo,
    background_tasks: BackgroundTasks,
):
    """
    Start a new backtest
    
    This initiates a background task that runs the backtest.
    Use the returned task_id to poll for status.
    """
    # Verify bot exists
    bot = bot_repo.get_by_id(request.bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {request.bot_id} not found"
        )
    
    # Validate date range
    if request.start_date >= request.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before end_date"
        )
    
    # Create task ID
    task_id = str(uuid4())
    
    # Initialize result
    result = BacktestResult(
        task_id=task_id,
        bot_id=request.bot_id,
        status="pending",
        progress=0.0,
        started_at=datetime.now(),
    )
    _backtest_results[task_id] = result
    
    # Add background task
    background_tasks.add_task(
        run_backtest_task,
        task_id=task_id,
        bot_id=request.bot_id,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_balance=request.initial_balance,
        symbols=request.symbols,
        max_cycles=request.max_cycles,
    )
    
    return APIResponse(
        data=result,
        message="Backtest started. Poll /backtests/{task_id} for status."
    )


@router.get("/{task_id}", response_model=APIResponse[BacktestResult])
async def get_backtest_status(
    task_id: str,
    api_key: APIKey,
):
    """
    Get backtest status and results
    """
    if task_id not in _backtest_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with task_id {task_id} not found"
        )
    
    return APIResponse(data=_backtest_results[task_id])


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_backtest(
    task_id: str,
    api_key: APIKey,
):
    """
    Cancel a running backtest (if possible)
    """
    if task_id not in _backtest_results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backtest with task_id {task_id} not found"
        )
    
    result = _backtest_results[task_id]
    if result.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backtest already completed"
        )
    
    result.status = "cancelled"
    result.completed_at = datetime.now()


@router.get("", response_model=APIResponse[list])
async def list_backtests(
    api_key: APIKey,
    bot_id: Optional[int] = None,
    status: Optional[str] = None,
):
    """
    List all backtests
    """
    results = list(_backtest_results.values())
    
    if bot_id:
        results = [r for r in results if r.bot_id == bot_id]
    if status:
        results = [r for r in results if r.status == status]
    
    # Sort by started_at descending
    results.sort(key=lambda r: r.started_at, reverse=True)
    
    return APIResponse(data=results)


# =============================================================================
# Background Task
# =============================================================================

async def run_backtest_task(
    task_id: str,
    bot_id: int,
    start_date: datetime,
    end_date: datetime,
    initial_balance: float,
    symbols: Optional[list] = None,
    max_cycles: Optional[int] = None,
):
    """
    Background task that runs the backtest
    """
    import sys
    from pathlib import Path
    
    # Add packages to path
    project_root = Path(__file__).parent.parent.parent.parent.parent
    sys.path.insert(0, str(project_root / "packages"))
    
    result = _backtest_results[task_id]
    result.status = "running"
    
    try:
        from langtrader_core.data import SessionLocal
        from langtrader_core.backtest.engine import BacktestEngine
        
        # Create backtest engine
        engine = BacktestEngine(
            bot_id=bot_id,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            symbols=symbols,
            max_cycles=max_cycles,
        )
        
        # Initialize with database session
        session = SessionLocal()
        try:
            await engine.initialize(session)
            
            # Run backtest
            report = await engine.run()
            
            # Update result
            result.status = "completed"
            result.progress = 100.0
            result.total_return = report.get("total_return", 0)
            result.return_pct = report.get("return_pct", 0)
            result.final_balance = report.get("final_balance", initial_balance)
            result.total_trades = report.get("total_trades", 0)
            result.win_rate = report.get("win_rate", 0)
            result.sharpe_ratio = report.get("sharpe_ratio", 0)
            result.max_drawdown = report.get("max_drawdown", 0)
            result.profit_factor = report.get("profit_factor", 0)
            result.completed_at = datetime.now()
            result.duration_seconds = int(
                (result.completed_at - result.started_at).total_seconds()
            )
            
        finally:
            await engine.cleanup()
            session.close()
    
    except Exception as e:
        result.status = "failed"
        result.error = str(e)
        result.completed_at = datetime.now()

