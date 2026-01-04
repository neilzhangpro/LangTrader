"""
Bot-related API Schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
# Dict 已在 typing 中导入


# =============================================================================
# Response Models
# =============================================================================

class BotSummary(BaseModel):
    """Bot list item (minimal info)"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    display_name: Optional[str] = None
    is_active: bool
    trading_mode: str
    exchange_id: int
    workflow_id: int
    created_at: datetime
    last_active_at: Optional[datetime] = None


class BotDetail(BaseModel):
    """Bot full details"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    prompt: Optional[str] = None
    
    # Relationships
    exchange_id: int
    workflow_id: int
    llm_id: Optional[int] = None
    
    # Status
    is_active: bool
    trading_mode: str
    
    # Tracing
    enable_tracing: bool = True
    tracing_project: str = "langtrader_pro"
    
    # Trading parameters
    max_concurrent_symbols: int = 5
    cycle_interval_seconds: int = 180
    max_leverage: int = 1
    max_position_size_percent: Decimal = Decimal("10.00")
    max_total_positions: int = 5
    
    # Quantitative signal config
    quant_signal_weights: Optional[Dict[str, float]] = None
    quant_signal_threshold: int = 50
    
    # Risk management
    risk_limits: Optional[Dict[str, Any]] = None
    
    # Balance
    initial_balance: Optional[Decimal] = None
    current_balance: Optional[Decimal] = None
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_active_at: Optional[datetime] = None
    created_by: Optional[str] = None


class BotStatus(BaseModel):
    """
    Real-time bot status
    
    从状态文件读取的详细运行信息
    """
    bot_id: int
    bot_name: str
    is_running: bool
    is_active: bool
    trading_mode: str
    current_cycle: int = 0
    last_cycle_at: Optional[str] = None  # ISO 格式时间字符串
    open_positions: int = 0
    symbols_trading: List[str] = Field(default_factory=list)
    uptime_seconds: Optional[int] = None
    error_message: Optional[str] = None
    
    # 新增：从状态文件读取的详细信息
    balance: Optional[float] = None  # 当前余额
    initial_balance: Optional[float] = None  # 初始余额
    last_decision: Optional[str] = None  # 最后一次决策摘要
    state: str = "unknown"  # 运行状态: running, idle, error, stopped


# =============================================================================
# Request Models
# =============================================================================

class BotCreateRequest(BaseModel):
    """Create bot request"""
    name: str = Field(..., min_length=1, max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    prompt: str = Field(default="default.txt")
    
    # Required relationships
    exchange_id: int
    workflow_id: int
    llm_id: Optional[int] = None
    
    # Trading mode
    trading_mode: str = Field(default="paper", pattern="^(paper|live|backtest)$")
    
    # Optional parameters with defaults
    max_concurrent_symbols: int = Field(default=5, ge=1, le=50)
    cycle_interval_seconds: int = Field(default=180, ge=60, le=3600)
    max_leverage: int = Field(default=1, ge=1, le=100)
    max_position_size_percent: Decimal = Field(default=Decimal("10.00"), ge=1, le=100)
    
    # Quantitative config
    quant_signal_weights: Optional[Dict[str, float]] = None
    quant_signal_threshold: int = Field(default=50, ge=0, le=100)
    
    # Risk limits
    risk_limits: Optional[Dict[str, Any]] = None


class BotUpdateRequest(BaseModel):
    """Update bot request (all fields optional)"""
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    prompt: Optional[str] = None
    
    # Relationships
    exchange_id: Optional[int] = None
    workflow_id: Optional[int] = None
    llm_id: Optional[int] = None
    
    # Status
    is_active: Optional[bool] = None
    trading_mode: Optional[str] = Field(None, pattern="^(paper|live|backtest)$")
    
    # Tracing
    enable_tracing: Optional[bool] = None
    tracing_project: Optional[str] = None
    
    # Trading parameters
    max_concurrent_symbols: Optional[int] = Field(None, ge=1, le=50)
    cycle_interval_seconds: Optional[int] = Field(None, ge=60, le=3600)
    max_leverage: Optional[int] = Field(None, ge=1, le=100)
    max_position_size_percent: Optional[Decimal] = Field(None, ge=1, le=100)
    
    # Quantitative config
    quant_signal_weights: Optional[Dict[str, float]] = None
    quant_signal_threshold: Optional[int] = Field(None, ge=0, le=100)
    
    # Risk limits
    risk_limits: Optional[Dict[str, Any]] = None


class BotStartRequest(BaseModel):
    """Start bot request (optional parameters)"""
    symbols: Optional[List[str]] = Field(
        None, 
        description="Override default symbol selection"
    )
    dry_run: bool = Field(
        default=False, 
        description="Run without executing trades"
    )


# =============================================================================
# Position & Balance Models
# =============================================================================

class PositionInfo(BaseModel):
    """持仓信息"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float  # 持仓数量
    entry_price: float  # 入场价格
    mark_price: float  # 标记价格
    unrealized_pnl: float  # 未实现盈亏
    leverage: int = 1  # 杠杆倍数
    margin_used: float = 0.0  # 使用的保证金
    liquidation_price: Optional[float] = None  # 强平价格


class BalanceInfo(BaseModel):
    """余额信息"""
    bot_id: int
    bot_name: str
    exchange_id: int
    total_usd: float
    balances: Dict[str, float] = Field(default_factory=dict)  # {USDT: 1000, USDC: 500}
    initial_balance: Optional[float] = None
    current_balance: Optional[float] = None
    pnl_usd: Optional[float] = None  # 盈亏
    pnl_percent: Optional[float] = None  # 盈亏百分比
    updated_at: datetime

