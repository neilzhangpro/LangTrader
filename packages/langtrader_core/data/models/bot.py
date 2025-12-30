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
    llm_id: int = Field(foreign_key="llm_configs.id") # 使用的LLM配置
    
    # 状态管理
    is_active: bool = Field(default=True)
    
    # 交易模式
    trading_mode: str = Field(default="paper")  # paper, live, backtest
    
    # 追踪配置
    enable_tracing: bool = Field(default=True)
    tracing_project: str = Field(default="langtrader_pro")
    tracing_key: Optional[str] = Field(default=None)
    
    # 运行参数
    max_concurrent_symbols: int = Field(default=5)
    cycle_interval_seconds: int = Field(default=180)
    
    # 风险管理
    max_position_size_percent: Decimal = Field(default=Decimal("10.00"))
    max_total_positions: int = Field(default=5)
    max_leverage: int = Field(default=1)
    
    # 量化信号配置
    quant_signal_weights: Optional[Dict[str, float]] = Field(
        default={"trend": 0.4, "momentum": 0.3, "volume": 0.2, "sentiment": 0.1},
        sa_column=Column(JSON)
    )
    quant_signal_threshold: int = Field(default=50)
    
    # 动态风险管理配置
    risk_limits: Optional[Dict[str, Any]] = Field(
        default={
            "max_total_exposure_pct": 0.8,
            "max_consecutive_losses": 5,
            "max_single_symbol_pct": 0.3
        },
        sa_column=Column(JSON)
    )
    
    # 资金管理
    initial_balance: Optional[Decimal] = None
    current_balance: Optional[Decimal] = None
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_active_at: Optional[datetime] = None
    
    # 创建者
    created_by: Optional[str] = None