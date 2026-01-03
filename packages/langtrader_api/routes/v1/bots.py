"""
Bot Management API Routes
"""
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional
from datetime import datetime

from langtrader_api.dependencies import (
    APIKey, DbSession, BotRepo, ExchangeRepo, WorkflowRepo
)
from langtrader_api.schemas.base import APIResponse, PaginatedResponse
from langtrader_api.schemas.bots import (
    BotSummary, BotDetail, BotStatus,
    BotCreateRequest, BotUpdateRequest, BotStartRequest
)
from langtrader_api.services.bot_manager import bot_manager
from langtrader_core.data.models.bot import Bot

router = APIRouter(prefix="/bots", tags=["Bots"])


# =============================================================================
# List & Get
# =============================================================================

@router.get("", response_model=APIResponse[PaginatedResponse[BotSummary]])
async def list_bots(
    api_key: APIKey,
    bot_repo: BotRepo,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    trading_mode: Optional[str] = Query(None, description="Filter by trading mode"),
):
    """
    List all bots with pagination and filters
    """
    # Get all bots (simple implementation, can be optimized)
    all_bots = bot_repo.session.query(Bot).all()
    
    # Apply filters
    filtered = all_bots
    if is_active is not None:
        filtered = [b for b in filtered if b.is_active == is_active]
    if trading_mode:
        filtered = [b for b in filtered if b.trading_mode == trading_mode]
    
    total = len(filtered)
    
    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]
    
    return APIResponse(
        data=PaginatedResponse.create(
            items=[BotSummary.model_validate(b) for b in items],
            total=total,
            page=page,
            page_size=page_size
        )
    )


@router.get("/{bot_id}", response_model=APIResponse[BotDetail])
async def get_bot(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
):
    """
    Get bot details by ID
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    return APIResponse(data=BotDetail.model_validate(bot))


# =============================================================================
# Create & Update
# =============================================================================

@router.post("", response_model=APIResponse[BotDetail], status_code=status.HTTP_201_CREATED)
async def create_bot(
    request: BotCreateRequest,
    api_key: APIKey,
    bot_repo: BotRepo,
    exchange_repo: ExchangeRepo,
    workflow_repo: WorkflowRepo,
    db: DbSession,
):
    """
    Create a new bot
    """
    # Check if name already exists
    existing = bot_repo.get_by_name(request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bot with name '{request.name}' already exists"
        )
    
    # Validate exchange exists
    exchange = exchange_repo.get_by_id(request.exchange_id)
    if not exchange:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Exchange with id {request.exchange_id} not found"
        )
    
    # Validate workflow exists
    workflow = workflow_repo.get_workflow(request.workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workflow with id {request.workflow_id} not found"
        )
    
    # Create bot
    bot = Bot(
        name=request.name,
        display_name=request.display_name,
        description=request.description,
        prompt=request.prompt,
        exchange_id=request.exchange_id,
        workflow_id=request.workflow_id,
        llm_id=request.llm_id,
        trading_mode=request.trading_mode,
        max_concurrent_symbols=request.max_concurrent_symbols,
        cycle_interval_seconds=request.cycle_interval_seconds,
        max_leverage=request.max_leverage,
        max_position_size_percent=request.max_position_size_percent,
        quant_signal_weights=request.quant_signal_weights,
        quant_signal_threshold=request.quant_signal_threshold,
        risk_limits=request.risk_limits,
    )
    
    db.add(bot)
    db.commit()
    db.refresh(bot)
    
    return APIResponse(
        data=BotDetail.model_validate(bot),
        message=f"Bot '{bot.name}' created successfully"
    )


@router.patch("/{bot_id}", response_model=APIResponse[BotDetail])
async def update_bot(
    bot_id: int,
    request: BotUpdateRequest,
    api_key: APIKey,
    bot_repo: BotRepo,
    db: DbSession,
):
    """
    Update bot configuration
    
    Only provided fields will be updated.
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # Check if bot is running
    if bot_manager.is_running(bot_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot update a running bot. Stop it first."
        )
    
    # Update fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bot, field, value)
    
    bot.updated_at = datetime.now()
    db.commit()
    db.refresh(bot)
    
    return APIResponse(
        data=BotDetail.model_validate(bot),
        message=f"Bot '{bot.name}' updated successfully"
    )


@router.delete("/{bot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bot(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    db: DbSession,
):
    """
    Delete a bot (soft delete - sets is_active=False)
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # Check if bot is running
    if bot_manager.is_running(bot_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a running bot. Stop it first."
        )
    
    bot.is_active = False
    bot.updated_at = datetime.now()
    db.commit()


# =============================================================================
# Bot Control
# =============================================================================

@router.get("/{bot_id}/status", response_model=APIResponse[BotStatus])
async def get_bot_status(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
):
    """
    Get real-time bot status
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    is_running = bot_manager.is_running(bot_id)
    process_info = bot_manager.get_process_info(bot_id)
    
    status_data = BotStatus(
        bot_id=bot_id,
        bot_name=bot.name,
        is_running=is_running,
        is_active=bot.is_active,
        trading_mode=bot.trading_mode,
        current_cycle=process_info.get("cycle", 0) if process_info else 0,
        last_cycle_at=bot.last_active_at,
        open_positions=0,  # TODO: Get from trader
        symbols_trading=[],  # TODO: Get from state
        uptime_seconds=process_info.get("uptime") if process_info else None,
        error_message=process_info.get("error") if process_info else None,
    )
    
    return APIResponse(data=status_data)


@router.post("/{bot_id}/start", response_model=APIResponse[dict])
async def start_bot(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    request: BotStartRequest = None,
):
    """
    Start a trading bot
    
    This will spawn a new process running the bot.
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    if not bot.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot start an inactive bot"
        )
    
    if bot_manager.is_running(bot_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bot is already running"
        )
    
    # Start the bot
    try:
        bot_manager.start_bot(bot_id)
        return APIResponse(
            data={"bot_id": bot_id, "action": "started"},
            message=f"Bot '{bot.name}' is starting..."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start bot: {str(e)}"
        )


@router.post("/{bot_id}/stop", response_model=APIResponse[dict])
async def stop_bot(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
):
    """
    Stop a running bot
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    if not bot_manager.is_running(bot_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot is not running"
        )
    
    # Stop the bot
    try:
        bot_manager.stop_bot(bot_id)
        return APIResponse(
            data={"bot_id": bot_id, "action": "stopped"},
            message=f"Bot '{bot.name}' is stopping..."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop bot: {str(e)}"
        )


@router.post("/{bot_id}/restart", response_model=APIResponse[dict])
async def restart_bot(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
):
    """
    Restart a bot (stop then start)
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # Stop if running
    if bot_manager.is_running(bot_id):
        bot_manager.stop_bot(bot_id)
    
    # Start
    bot_manager.start_bot(bot_id)
    
    return APIResponse(
        data={"bot_id": bot_id, "action": "restarted"},
        message=f"Bot '{bot.name}' is restarting..."
    )


# =============================================================================
# Positions & Balance
# =============================================================================

@router.get("/{bot_id}/positions", response_model=APIResponse[list])
async def get_bot_positions(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    db: DbSession,
):
    """
    获取 Bot 当前持仓
    
    从交易所实时获取当前持仓信息
    """
    from langtrader_api.schemas.bots import PositionInfo
    
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # 获取交易所配置
    from langtrader_core.data.repositories.exchange import ExchangeRepository
    exchange_repo = ExchangeRepository(db)
    ex = exchange_repo.get_by_id(bot.exchange_id)
    
    if not ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot's exchange configuration not found"
        )
    
    try:
        import ccxt
        
        # 创建交易所实例
        exchange_class = getattr(ccxt, ex['type'], None)
        if not exchange_class:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported exchange type: {ex['type']}"
            )
        
        config = {
            'apiKey': ex['apikey'],
            'secret': ex['secretkey'],
        }
        if ex.get('uid'):
            config['uid'] = ex['uid']
        if ex.get('password'):
            config['password'] = ex['password']
        if ex.get('testnet'):
            config['sandbox'] = True
        
        exchange_instance = exchange_class(config)
        
        # 获取持仓
        positions = exchange_instance.fetch_positions()
        
        # 过滤有效持仓
        result = []
        for pos in positions:
            size = float(pos.get('contracts', 0) or pos.get('contractSize', 0) or 0)
            if abs(size) > 0:
                result.append(PositionInfo(
                    symbol=pos.get('symbol', 'Unknown'),
                    side='long' if size > 0 else 'short',
                    size=abs(size),
                    entry_price=float(pos.get('entryPrice', 0) or 0),
                    mark_price=float(pos.get('markPrice', 0) or 0),
                    unrealized_pnl=float(pos.get('unrealizedPnl', 0) or 0),
                    leverage=int(pos.get('leverage', 1) or 1),
                    margin_used=float(pos.get('initialMargin', 0) or pos.get('margin', 0) or 0),
                    liquidation_price=float(pos.get('liquidationPrice', 0) or 0) if pos.get('liquidationPrice') else None,
                ))
        
        return APIResponse(data=result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch positions: {str(e)}"
        )


@router.get("/{bot_id}/balance", response_model=APIResponse[dict])
async def get_bot_balance(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    db: DbSession,
):
    """
    获取 Bot 关联交易所的账户余额
    
    返回 USDT/USDC 等稳定币余额及总余额
    """
    from datetime import datetime
    
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    # 获取交易所配置
    from langtrader_core.data.repositories.exchange import ExchangeRepository
    exchange_repo = ExchangeRepository(db)
    ex = exchange_repo.get_by_id(bot.exchange_id)
    
    if not ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bot's exchange configuration not found"
        )
    
    try:
        import ccxt
        
        # 创建交易所实例
        exchange_class = getattr(ccxt, ex['type'], None)
        if not exchange_class:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported exchange type: {ex['type']}"
            )
        
        config = {
            'apiKey': ex['apikey'],
            'secret': ex['secretkey'],
        }
        if ex.get('uid'):
            config['uid'] = ex['uid']
        if ex.get('password'):
            config['password'] = ex['password']
        if ex.get('testnet'):
            config['sandbox'] = True
        
        exchange_instance = exchange_class(config)
        
        # 获取余额
        balance = exchange_instance.fetch_balance()
        
        # 提取主要币种余额
        total_usd = 0.0
        balances = {}
        
        for currency in ['USDT', 'USDC', 'USD', 'BUSD']:
            if currency in balance.get('total', {}):
                amount = float(balance['total'][currency] or 0)
                if amount > 0:
                    balances[currency] = amount
                    total_usd += amount
        
        return APIResponse(
            data={
                "bot_id": bot_id,
                "bot_name": bot.name,
                "exchange_id": bot.exchange_id,
                "total_usd": total_usd,
                "balances": balances,
                "initial_balance": float(bot.initial_balance) if bot.initial_balance else None,
                "current_balance": float(bot.current_balance) if bot.current_balance else total_usd,
                "updated_at": datetime.now().isoformat(),
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch balance: {str(e)}"
        )


@router.get("/{bot_id}/logs", response_model=APIResponse[dict])
async def get_bot_logs(
    bot_id: int,
    api_key: APIKey,
    bot_repo: BotRepo,
    lines: int = Query(100, ge=10, le=1000, description="Number of log lines to return"),
):
    """
    获取 Bot 运行日志
    
    返回最近的日志内容
    """
    bot = bot_repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bot with id {bot_id} not found"
        )
    
    logs = bot_manager.get_logs(bot_id, lines=lines)
    
    return APIResponse(
        data={
            "bot_id": bot_id,
            "bot_name": bot.name,
            "lines_requested": lines,
            "logs": logs or "No logs available",
        }
    )

