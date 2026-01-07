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
    tracing_key: Optional[str] = None
    
    # Agent 搜索 KEY
    tavily_search_key: Optional[str] = None
    
    # Trading parameters
    max_concurrent_symbols: int = 5
    cycle_interval_seconds: int = 180
    max_leverage: int = 3
    
    # Quantitative signal config
    quant_signal_weights: Optional[Dict[str, float]] = None
    quant_signal_threshold: int = 50
    
    # Risk management
    risk_limits: Optional[Dict[str, Any]] = None
    
    # Dynamic config (trading timeframes and OHLCV limits)
    trading_timeframes: Optional[List[str]] = None
    ohlcv_limits: Optional[Dict[str, int]] = None
    indicator_configs: Optional[Dict[str, Any]] = None
    
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
    
    # Tracing config
    enable_tracing: bool = Field(default=True)
    tracing_project: str = Field(default="langtrader_pro", max_length=255)
    tracing_key: Optional[str] = Field(None, max_length=255)
    
    # Agent search key
    tavily_search_key: Optional[str] = Field(None, max_length=255)
    
    # Optional parameters with defaults
    max_concurrent_symbols: int = Field(default=5, ge=1, le=50)
    cycle_interval_seconds: int = Field(default=180, ge=60, le=3600)
    max_leverage: int = Field(default=3, ge=1, le=100)
    
    # Quantitative config
    quant_signal_weights: Optional[Dict[str, float]] = None
    quant_signal_threshold: int = Field(default=50, ge=0, le=100)
    
    # Risk limits
    risk_limits: Optional[Dict[str, Any]] = None
    
    # Dynamic config (trading timeframes and OHLCV limits)
    trading_timeframes: Optional[List[str]] = None
    ohlcv_limits: Optional[Dict[str, int]] = None
    indicator_configs: Optional[Dict[str, Any]] = None
    
    # Initial balance
    initial_balance: Optional[Decimal] = None


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
    tracing_key: Optional[str] = None
    
    # Agent search key
    tavily_search_key: Optional[str] = None
    
    # Trading parameters
    max_concurrent_symbols: Optional[int] = Field(None, ge=1, le=50)
    cycle_interval_seconds: Optional[int] = Field(None, ge=60, le=3600)
    max_leverage: Optional[int] = Field(None, ge=1, le=100)
    
    # Quantitative config
    quant_signal_weights: Optional[Dict[str, float]] = None
    quant_signal_threshold: Optional[int] = Field(None, ge=0, le=100)
    
    # Risk limits
    risk_limits: Optional[Dict[str, Any]] = None
    
    # Dynamic config (trading timeframes and OHLCV limits)
    trading_timeframes: Optional[List[str]] = None
    ohlcv_limits: Optional[Dict[str, int]] = None
    indicator_configs: Optional[Dict[str, Any]] = None
    
    # Initial balance
    initial_balance: Optional[Decimal] = None


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


# =============================================================================
# AI Debate Models (辩论决策展示)
# =============================================================================

class AnalystOutputSchema(BaseModel):
    """市场分析师输出"""
    symbol: str
    trend: str  # bullish/bearish/neutral
    key_levels: Optional[Dict[str, float]] = None  # {support: 100.5, resistance: 105.0}
    summary: str


class TraderSuggestionSchema(BaseModel):
    """交易员建议（Bull/Bear）"""
    symbol: str
    action: str  # long/short/wait
    confidence: int = Field(ge=0, le=100)
    allocation_pct: float = Field(ge=0, le=100)
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 6.0
    reasoning: str


class PortfolioDecisionSchema(BaseModel):
    """最终投资组合决策"""
    symbol: str
    action: str  # open_long/open_short/close_long/close_short/wait
    allocation_pct: float = 0.0
    confidence: int = 0
    leverage: int = 3
    stop_loss: Optional[float] = None  # 止损价格
    take_profit: Optional[float] = None  # 止盈价格
    priority: int = 99
    reasoning: str = ""


class BatchDecisionSchema(BaseModel):
    """批量决策结果"""
    decisions: List[PortfolioDecisionSchema] = Field(default_factory=list)
    total_allocation_pct: float = 0.0
    cash_reserve_pct: float = 100.0
    strategy_rationale: str = ""


class DebateResult(BaseModel):
    """
    AI 辩论完整结果
    
    展示多空辩论的完整过程：
    - Phase 1: 分析师分析
    - Phase 2: 多头/空头交易员建议
    - Phase 3: 风控经理最终决策
    """
    # Phase 1: 分析师输出
    analyst_outputs: List[AnalystOutputSchema] = Field(default_factory=list)
    
    # Phase 2: 多空交易员建议
    bull_suggestions: List[TraderSuggestionSchema] = Field(default_factory=list)
    bear_suggestions: List[TraderSuggestionSchema] = Field(default_factory=list)
    
    # Phase 3: 最终决策
    final_decision: Optional[BatchDecisionSchema] = None
    
    # 元信息
    debate_summary: str = ""
    completed_at: Optional[str] = None

