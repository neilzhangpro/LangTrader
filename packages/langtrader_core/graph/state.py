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
# 注：OrderStatus 已删除，未被任何代码使用


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

    price: float          # 入场价格
    average: float        # 平均价格
    amount: float         # 持仓数量（币的数量）
    leverage: int = 1     # 杠杆倍数（默认 1 倍）

    trigger_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    
    @property
    def notional_value(self) -> float:
        """名义价值 = 数量 × 价格"""
        return self.amount * self.price
    
    @property
    def margin_used(self) -> float:
        """已用保证金 = 名义价值 / 杠杆"""
        return self.notional_value / self.leverage if self.leverage > 0 else self.notional_value


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
            # 新 bot：鼓励探索，不要过度保守
            text = "Historical Performance:\n"
            text += "-------------------\n"
            text += "  🆕 新策略启动阶段（无历史交易）\n"
            text += "  建议: 积极探索，寻找高信心度机会\n"
            text += "  注意: 首次交易建议小仓位（10-15%）试探市场\n"
            text += "-------------------\n"
            return text
        
        text = "Historical Performance:\n"
        text += "-------------------\n"
        text += f"  Total Trades: {self.total_trades}\n"
        text += f"  Win Rate: {self.win_rate:.1f}%\n"
        text += f"  Sharpe Ratio: {self.sharpe_ratio:.2f}\n"
        text += f"  Avg Return per Trade: {self.avg_return_pct:.2f}%\n"
        text += f"  Total Return: ${self.total_return_usd:.2f}\n"
        text += f"  Max Drawdown: {self.max_drawdown*100:.2f}%\n"
        
        # 根据夏普比率给出策略建议（更平衡的建议）
        if self.sharpe_ratio < -0.5:
            text += "\n  ⚠️ WARNING: Sharpe < -0.5 (持续亏损)\n"
            text += "  建议: 降低仓位至 10%，只做信心度 > 75 的交易\n"
        elif self.sharpe_ratio < 0:
            text += "\n  📉 CAUTION: Sharpe < 0 (轻微亏损)\n"
            text += "  建议: 降低仓位至 15%，优选信心度 > 65 的交易\n"
        elif self.sharpe_ratio < 0.3:
            text += "\n  📊 NEUTRAL: Sharpe 0~0.3 (策略探索中)\n"
            text += "  建议: 正常交易，信心度 > 55 即可尝试\n"
        elif self.sharpe_ratio < 0.7:
            text += "\n  📈 GOOD: Sharpe 0.3~0.7 (策略有效)\n"
            text += "  建议: 可以正常配置仓位，保持当前策略\n"
        else:
            text += "\n  🚀 EXCELLENT: Sharpe > 0.7 (优异表现)\n"
            text += "  建议: 策略有效，可适度扩大仓位\n"
        
        text += "-------------------\n"
        return text


# -------------------------
# Decision / Execution
# -------------------------

DecisionAction = Literal[
    "open_long", "open_short",
    "close_long", "close_short",
    "wait",  # 不操作，观望（移除 hold 避免歧义）
]


class AIDecision(BaseModel):
    """AI 决策结果（内部使用，由 PortfolioDecision 转换而来）"""
    model_config = ConfigDict(extra="forbid")

    symbol: str
    action: DecisionAction

    leverage: int = 1
    position_size_usd: float = 0.0

    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    confidence: int = 0  # 统一使用 int (0-100)
    risk_usd: float = 0.0

    risk_approved: bool = False

    reasons: List[str] = Field(default_factory=list)


# -------------------------
# Batch Decision (NoFx-style)
# -------------------------

class PortfolioDecision(BaseModel):
    """
    单个币种的投资组合决策（批量决策模式）
    
    设计参考 NoFx prompt_builder.go 的 Decision 结构：
    - 包含仓位分配百分比（allocation_pct）用于协调多币种仓位
    - 包含优先级（priority）用于执行顺序控制
    - 包含详细推理过程（reasoning）便于回溯分析
    """
    # OpenAI Structured Output 要求 additionalProperties: false
    model_config = ConfigDict(extra="forbid")
    
    # 基础信息
    symbol: str
    action: DecisionAction
    
    # 仓位分配
    allocation_pct: float = 0.0  # 占总余额的百分比 (0-100)
    position_size_usd: float = 0.0  # 实际仓位金额
    leverage: int = 1
    
    # 止盈止损
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # 决策元信息
    confidence: int = 0  # 0-100
    reasoning: str = ""  # 详细推理过程（NoFx 要求必填）
    priority: int = 0  # 执行优先级，数字越小优先级越高
    
    # 兼容旧版字段
    risk_approved: bool = False


class BatchDecisionResult(BaseModel):
    """
    批量决策结果（一次 LLM 调用输出所有币种的决策）
    
    设计原则（参考 NoFx）：
    - 所有决策的 allocation_pct 总和不超过 80%
    - 保留至少 20% 现金储备
    - 包含整体策略说明
    """
    # OpenAI Structured Output 要求 additionalProperties: false
    model_config = ConfigDict(extra="forbid")
    
    # 所有币种的决策列表
    decisions: List[PortfolioDecision] = Field(default_factory=list)
    
    # 仓位汇总
    total_allocation_pct: float = 0.0  # 总仓位占比
    cash_reserve_pct: float = 20.0  # 现金储备比例
    
    # 整体策略说明
    strategy_rationale: str = ""


# -------------------------
# Debate Decision Models (四角色辩论)
# -------------------------

class AnalystOutput(BaseModel):
    """市场分析师输出"""
    model_config = ConfigDict(extra="forbid")
    
    symbol: str
    trend: Literal["bullish", "bearish", "neutral"] = Field(description="趋势判断")
    key_levels: Optional[Dict[str, float]] = Field(default=None, description="关键价位: support/resistance，如 {'support': 100.5, 'resistance': 105.0}")
    summary: str = Field(description="技术分析总结")


class AnalystOutputList(BaseModel):
    """
    市场分析师输出列表（用于一次性返回多币种分析）
    
    LLM with_structured_output 默认只返回单个对象，
    使用此包装类型可让 Analyst 一次性输出所有币种的分析结果。
    """
    model_config = ConfigDict(extra="forbid")
    
    outputs: List[AnalystOutput] = Field(description="所有币种的分析结果")


class TraderSuggestion(BaseModel):
    """交易员建议（Bull/Bear）"""
    model_config = ConfigDict(extra="forbid")
    
    symbol: str
    action: Literal["long", "short", "wait"] = Field(description="建议动作")
    confidence: int = Field(ge=0, le=100, description="信心度 0-100")
    allocation_pct: float = Field(ge=0, le=30, description="建议仓位 0-30%")
    stop_loss_pct: float = Field(ge=0, le=10, default=2.0, description="止损比例 0-10%")
    take_profit_pct: float = Field(ge=0, le=50, default=6.0, description="止盈比例 0-50%")
    reasoning: str = Field(description="决策理由")


class DebateRound(BaseModel):
    """
    单轮辩论记录
    
    记录多轮辩论中每一轮的 Bull 和 Bear 观点，
    用于追溯辩论过程和分析决策质量。
    """
    model_config = ConfigDict(extra="forbid")
    
    round_number: int = Field(description="轮次编号（从 1 开始）")
    symbol: str = Field(description="辩论的币种")
    bull_opinion: str = Field(description="多头交易员观点")
    bear_opinion: str = Field(description="空头交易员观点")
    bull_action: Optional[Literal["long", "short", "wait"]] = Field(default=None, description="多头建议动作")
    bear_action: Optional[Literal["long", "short", "wait"]] = Field(default=None, description="空头建议动作")


class RiskReview(BaseModel):
    """风控审核结果"""
    model_config = ConfigDict(extra="forbid")
    
    approved: bool
    total_allocation_pct: float = Field(description="审核后的总仓位")
    modifications: Optional[List[Dict[str, Any]]] = Field(default=None, description="修正建议")
    concerns: Optional[List[str]] = Field(default=None, description="风险关注点")


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
# Debate Decision Result (辩论决策完整结果)
# -------------------------

class DebateDecisionResult(BaseModel):
    """
    辩论决策完整结果（记录整个辩论过程）
    
    与 batch_decision 平级，用于模式2的辩论决策节点
    """
    model_config = ConfigDict(extra="forbid")
    
    # Phase 1: 分析师输出
    analyst_outputs: List[AnalystOutput] = Field(default_factory=list)
    
    # Phase 2: 多空交易员建议（最终轮结果）
    bull_suggestions: List[TraderSuggestion] = Field(default_factory=list)
    bear_suggestions: List[TraderSuggestion] = Field(default_factory=list)
    
    # Phase 2: 多轮辩论记录（每个币种的辩论历史）
    debate_rounds: Optional[List[DebateRound]] = Field(
        default=None,
        description="多轮辩论的完整记录，按轮次和币种排列"
    )
    
    # Phase 3: 风控审核（可选，目前直接输出最终决策）
    risk_review: Optional[RiskReview] = None
    
    # 最终决策（复用 BatchDecisionResult 格式，与 execution 兼容）
    final_decision: Optional[BatchDecisionResult] = None
    
    # 元信息
    debate_summary: str = ""  # 辩论过程摘要
    completed_at: Optional[datetime] = None


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

    # 批量决策结果（模式1: 用户提示词）
    batch_decision: Optional[BatchDecisionResult] = None
    
    # 辩论决策结果（模式2: 多空辩论）
    debate_decision: Optional[DebateDecisionResult] = None

    # 绩效指标（由 Decision 节点计算并注入）
    performance: Optional[PerformanceMetrics] = None

    # 告警信息
    alerts: List[str] = Field(default_factory=list)
    
    def reset_for_new_cycle(self):
        """
        重置每轮临时数据（保留 bot_id、prompt_name、initial_balance）
        
        在每个交易周期开始时调用，清理上一轮的状态数据，
        避免数据残留影响新一轮决策。
        
        注意：alerts 不在此处清空，保留到下一轮决策时供 AI 读取，
        由 debate_decision/batch_decision 节点读取后再清空。
        """
        self.symbols = []
        self.market_data = {}
        self.batch_decision = None
        self.debate_decision = None
        self.performance = None
        # alerts 保留：用于跨周期传递执行失败信息给 AI
        # account 和 positions 由 run_once 单独刷新