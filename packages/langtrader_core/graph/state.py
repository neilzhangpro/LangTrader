from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, ConfigDict, Field


# -------------------------
# Order Types (统一类型定义)
# -------------------------

OrderType = Literal["market", "limit", "stop", "stop_limit", "take_profit", "trailing_stop"]
OrderSide = Literal["buy", "sell"]
PositionSide = Literal["long", "short", "both"]
OrderStatus = Literal["open", "closed", "canceled", "expired", "rejected", "pending"]


# -------------------------
# Domain / Portfolio
# -------------------------

class Account(BaseModel):
    """账户快照"""
    model_config = ConfigDict(extra="allow")
    timestamp: datetime
    free: Dict[str, float] = Field(default_factory=dict)
    used: Dict[str, float] = Field(default_factory=dict)
    total: Dict[str, float] = Field(default_factory=dict)
    debt: Dict[str, float] = Field(default_factory=dict)
    info: Optional[Dict[str, Any]] = None


class Position(BaseModel):
    """持仓信息"""
    model_config = ConfigDict(extra="allow")

    id: str
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["limit", "market"]
    status: Literal["open", "closed", "canceled", "expired", "rejected"]

    datetime: datetime
    last_trade_timestamp: Optional[datetime] = None

    price: float
    average: float
    amount: float

    trigger_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None


# -------------------------
# Order Management
# -------------------------

class OrderResult(BaseModel):
    """统一的订单结果"""
    model_config = ConfigDict(extra="allow")
    
    success: bool
    order_id: Optional[str] = None
    symbol: Optional[str] = None
    status: Optional[str] = None
    
    # 成交信息
    filled: float = 0.0
    remaining: float = 0.0
    average: Optional[float] = None
    fee: Optional[float] = None
    
    # 原始数据
    raw: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class OpenPositionResult(BaseModel):
    """一键开仓结果"""
    model_config = ConfigDict(extra="allow")
    
    main: Optional[OrderResult] = None
    stop_loss: Optional[OrderResult] = None
    take_profit: Optional[OrderResult] = None


# -------------------------
# Performance Metrics
# -------------------------

class PerformanceMetrics(BaseModel):
    """绩效指标（用于注入 prompt）"""
    model_config = ConfigDict(extra="allow")
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_return_pct: float = 0.0
    total_return_usd: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    
    def to_prompt_text(self) -> str:
        """转换为 prompt 文本"""
        if self.total_trades == 0:
            return "No historical trades yet.\n"
        
        text = "Historical Performance:\n"
        text += "-------------------\n"
        text += f"  Total Trades: {self.total_trades}\n"
        text += f"  Win Rate: {self.win_rate:.1f}%\n"
        text += f"  Sharpe Ratio: {self.sharpe_ratio:.2f}\n"
        text += f"  Avg Return per Trade: {self.avg_return_pct:.2f}%\n"
        text += f"  Total Return: ${self.total_return_usd:.2f}\n"
        text += f"  Max Drawdown: {self.max_drawdown:.2f}%\n"
        
        # 根据夏普比率给出策略建议
        if self.sharpe_ratio < -0.5:
            text += "\n  WARNING: Sharpe < -0.5 (持续亏损)\n"
            text += "  建议: 停止交易，只观望，至少6个周期不开仓\n"
        elif self.sharpe_ratio < 0:
            text += "\n  CAUTION: Sharpe < 0 (轻微亏损)\n"
            text += "  建议: 只做信心度>80的交易，减少频率\n"
        elif self.sharpe_ratio > 0.7:
            text += "\n  EXCELLENT: Sharpe > 0.7 (优异表现)\n"
            text += "  建议: 可适度扩大仓位\n"
        
        text += "-------------------\n"
        return text


# -------------------------
# Decision / Execution
# -------------------------

DecisionAction = Literal[
    "open_long", "open_short",
    "close_long", "close_short",
    "hold", "wait",
]


class AIDecision(BaseModel):
    """AI 决策结果（LLM structured output）"""
    model_config = ConfigDict(extra="forbid")

    symbol: str
    action: DecisionAction

    leverage: int = 1
    position_size_usd: float = 0.0

    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    confidence: float = 0.0
    risk_usd: float = 0.0

    risk_approved: bool = False

    reasons: List[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    """执行结果"""
    model_config = ConfigDict(extra="allow")

    symbol: str
    action: DecisionAction
    status: Literal["skipped", "pending", "success", "failed"]

    message: str = ""
    order_id: Optional[str] = None
    executed_price: Optional[float] = None
    executed_amount: Optional[float] = None
    fee_paid: Optional[float] = None
    
    # 关联的订单结果
    orders: Optional[OpenPositionResult] = None


# -------------------------
# Per-symbol record
# -------------------------

class RunRecord(BaseModel):
    """单个 symbol 的一次运行记录"""
    model_config = ConfigDict(extra="allow")

    run_id: str
    cycle_id: str
    symbol: str
    cycle_time: datetime

    # 市场分析（纯文本，由 market_analyzer 生成）
    market_analysis: Optional[str] = None
    analyzed_at: Optional[str] = None

    # AI 决策
    decision: Optional[AIDecision] = None

    # 执行结果
    execution: Optional[ExecutionResult] = None

    # 时间记录
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


# -------------------------
# Final State
# -------------------------

class State(BaseModel):
    """LangGraph 主状态"""
    model_config = ConfigDict(extra="allow")

    # 基础信息
    bot_id: int
    prompt_name: str = "default.txt"
    initial_balance: Optional[float] = None

    # 当前周期的币种列表
    symbols: List[str] = Field(default_factory=list)

    # 市场数据 {symbol: {'3m': ohlcv, '4h': ohlcv, 'indicators': {...}}}
    market_data: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # 账户快照
    account: Optional[Account] = None
    positions: List[Position] = Field(default_factory=list)

    # 每个 symbol 的运行记录（核心字段）
    runs: Dict[str, RunRecord] = Field(default_factory=dict)

    # 绩效指标（由 Decision 节点计算并注入）
    performance: Optional[PerformanceMetrics] = None

    # 告警信息
    alerts: List[str] = Field(default_factory=list)
