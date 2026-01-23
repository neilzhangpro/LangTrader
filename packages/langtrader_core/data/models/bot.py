# packages/langtrader_core/data/models/bot.py
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import JSON
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

class Bot(SQLModel, table=True):
    """
    交易机器人配置中心
    Bot 是核心配置单元，包含交易所、策略、运行参数等所有配置
    """
    __tablename__ = "bots"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    prompt: str = Field(default=None)
    # 基本信息
    name: str = Field(unique=True, index=True)
    display_name: Optional[str] = None
    description: Optional[str] = None
    
    # 核心关联
    exchange_id: int = Field(foreign_key="exchanges.id")
    workflow_id: int = Field(foreign_key="workflows.id")
    llm_id: Optional[int] = Field(default=None, foreign_key="llm_configs.id")  # 使用的LLM配置（可选）
    
    # 状态管理
    is_active: bool = Field(default=True)
    
    # 交易模式
    trading_mode: str = Field(default="paper")  # paper, live, backtest
    
    # 追踪配置
    enable_tracing: bool = Field(default=True)
    tracing_project: str = Field(default="langtrader_pro")
    tracing_key: Optional[str] = Field(default=None)
    
    # 运行参数
    cycle_interval_seconds: int = Field(default=180)
    max_leverage: int = Field(default=3)  # 最大杠杆倍数
    max_concurrent_symbols: int = Field(default=5)  # 最大同时交易币种数
    
    # 量化信号配置
    quant_signal_weights: Optional[Dict[str, float]] = Field(
        default={"trend": 0.4, "momentum": 0.3, "volume": 0.2, "sentiment": 0.1},
        sa_column=Column(JSON)
    )
    quant_signal_threshold: int = Field(default=45)
    
    # ==================== 风控硬约束配置 ====================
    # 所有风控参数集中在 risk_limits 字段，便于统一管理
    # 执行节点会在下单前检查这些约束
    # 注意：所有百分比参数统一使用小数格式（0.8 = 80%，0.15 = 15%）
    risk_limits: Optional[Dict[str, Any]] = Field(
        default={
            # ========== 仓位控制（小数格式：0.8 = 80%）==========
            "max_total_exposure_pct": 0.8,        # 总仓位上限 80%
            "max_single_symbol_pct": 0.3,         # 单币种上限 30%
            
            # ========== 杠杆控制 ==========
            "max_leverage": 5,                    # 最大杠杆倍数
            "default_leverage": 3,                # 推荐杠杆倍数
            
            # ========== 风险控制（小数格式）==========
            "max_consecutive_losses": 8,          # 连续亏损次数上限（触发后暂停交易）
            "max_daily_loss_pct": 0.05,           # 单日最大亏损 5%
            "max_drawdown_pct": 0.15,             # 最大回撤 15%（触发后暂停交易）
            
            # ========== 资金费率控制（小数格式：0.0005 = 0.05%）==========
            "max_funding_rate_pct": 0.0005,       # 资金费率上限 0.05%，超过时不开仓
            "funding_rate_check_enabled": True,   # 是否启用资金费率检查
            
            # ========== 订单约束 ==========
            "min_position_size_usd": 10.0,        # 最小开仓金额（USD）
            "max_position_size_usd": 5000.0,      # 最大开仓金额（USD）
            "min_risk_reward_ratio": 2.0,         # 最小风险回报比（盈亏比）
            
            # ========== 默认止损止盈（当 LLM 未设置时使用）==========
            "default_stop_loss_pct": 3.0,         # 默认止损比例 3%
            "default_take_profit_pct": 6.0,       # 默认止盈比例 6%（与止损配合 2:1 盈亏比）
            
            # ========== 开关控制 ==========
            "hard_stop_enabled": True,            # 是否启用硬止损
            "pause_on_consecutive_loss": True,    # 连续亏损时是否暂停
            "pause_on_max_drawdown": True,        # 触及最大回撤时是否暂停
            
            # ========== 追踪止损配置 ==========
            "trailing_stop_enabled": False,       # 是否启用追踪止损（默认关闭）
            "trailing_stop_trigger_pct": 3.0,     # 触发追踪的最小盈利 (3%)
            "trailing_stop_distance_pct": 1.5,    # 追踪距离 (1.5%)
            "trailing_stop_lock_profit_pct": 1.0, # 最少锁定利润 (1%)
        },
        sa_column=Column(JSON)
    )
    
    # 动态配置字段（新增）
    trading_timeframes: Optional[list] = Field(
        default=["3m", "4h"],
        sa_column=Column(JSON)
    )
    ohlcv_limits: Optional[Dict[str, int]] = Field(
        default={"3m": 100, "4h": 100},
        sa_column=Column(JSON)
    )
    indicator_configs: Optional[Dict[str, Any]] = Field(
        default={
            "ema_periods": [20, 50, 200],
            "rsi_period": 7,
            "macd_config": {"fast": 12, "slow": 26, "signal": 9},
            "atr_period": 14,
            "bollinger_period": 20,
            "bollinger_std": 2.0,
            "stochastic_k": 14,
            "stochastic_d": 3
        },
        sa_column=Column(JSON)
    )
    
    # 资金管理
    initial_balance: Optional[Decimal] = None
    current_balance: Optional[Decimal] = None

    # Agent搜索KEY
    tavily_search_key: str = Field(default=None)
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_active_at: Optional[datetime] = None
    
    # 创建者
    created_by: Optional[str] = None