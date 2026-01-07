"""
Dependency Injection for FastAPI
Integrates with langtrader_core services
"""
from typing import Annotated, Generator
from fastapi import Depends, HTTPException, Header, status
from sqlmodel import Session

from langtrader_core.data import SessionLocal, init_db
from langtrader_core.data.repositories.bot import BotRepository
from langtrader_core.data.repositories.trade_history import TradeHistoryRepository
from langtrader_core.data.repositories.workflow import WorkflowRepository
from langtrader_core.data.repositories.exchange import ExchangeRepository
from langtrader_core.data.repositories.llm_config import LLMConfigRepository
from langtrader_core.services.performance import PerformanceService
from langtrader_api.config import settings


# =============================================================================
# Database Session
# =============================================================================

def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# API Key Authentication
# =============================================================================

async def validate_api_key(
    x_api_key: str = Header(..., description="API Key for authentication")
) -> str:
    """
    Validate API Key from header
    
    Usage:
        @router.get("/protected")
        async def protected_route(api_key: APIKey):
            ...
    """
    if x_api_key not in settings.API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


# =============================================================================
# Repository Dependencies
# =============================================================================

def get_bot_repository(
    db: Annotated[Session, Depends(get_db)]
) -> BotRepository:
    """Get BotRepository instance"""
    return BotRepository(db)


def get_trade_history_repository(
    db: Annotated[Session, Depends(get_db)]
) -> TradeHistoryRepository:
    """Get TradeHistoryRepository instance"""
    return TradeHistoryRepository(db)


def get_workflow_repository(
    db: Annotated[Session, Depends(get_db)]
) -> WorkflowRepository:
    """Get WorkflowRepository instance"""
    return WorkflowRepository(db)


def get_exchange_repository(
    db: Annotated[Session, Depends(get_db)]
) -> ExchangeRepository:
    """Get ExchangeRepository instance"""
    return ExchangeRepository(db)


def get_llm_config_repository(
    db: Annotated[Session, Depends(get_db)]
) -> LLMConfigRepository:
    """Get LLMConfigRepository instance"""
    return LLMConfigRepository(db)


def get_performance_service(
    db: Annotated[Session, Depends(get_db)]
) -> PerformanceService:
    """Get PerformanceService instance"""
    return PerformanceService(db)


# =============================================================================
# Type Aliases for Clean Route Signatures
# =============================================================================

DbSession = Annotated[Session, Depends(get_db)]
APIKey = Annotated[str, Depends(validate_api_key)]
BotRepo = Annotated[BotRepository, Depends(get_bot_repository)]
TradeRepo = Annotated[TradeHistoryRepository, Depends(get_trade_history_repository)]
WorkflowRepo = Annotated[WorkflowRepository, Depends(get_workflow_repository)]
ExchangeRepo = Annotated[ExchangeRepository, Depends(get_exchange_repository)]
LLMConfigRepo = Annotated[LLMConfigRepository, Depends(get_llm_config_repository)]
PerfService = Annotated[PerformanceService, Depends(get_performance_service)]


# =============================================================================
# Startup/Shutdown Hooks
# =============================================================================

async def init_services():
    """Initialize services on application startup"""
    from langtrader_core.plugins.registry import registry
    from langtrader_core.plugins.auto_sync import PluginAutoSync
    from langtrader_core.data.models.workflow import Workflow
    from sqlmodel import select
    from datetime import datetime
    
    # 1. 初始化数据库表结构
    init_db()
    
    # 2. 发现所有插件（注册到内存）
    registry.discover_plugins("langtrader_core.graph.nodes")
    print(f"✅ Discovered {len(registry._metadata)} plugins")
    
    # 3. 确保数据库中有默认 Workflow
    db = SessionLocal()
    try:
        statement = select(Workflow)
        existing_workflows = db.exec(statement).all()
        
        if not existing_workflows:
            # 创建默认 workflow
            default_workflow = Workflow(
                name="debate_trading",
                display_name="Multi-Agent Debate Trading",
                version="1.0.0",
                description="AI multi-agent debate workflow for trading decisions",
                category="trading",
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(default_workflow)
            db.commit()
            db.refresh(default_workflow)
            workflow_id = default_workflow.id
            print(f"✅ Created default workflow: {default_workflow.name} (id={workflow_id})")
        else:
            workflow_id = existing_workflows[0].id
            print(f"ℹ️ Using existing workflow: {existing_workflows[0].name} (id={workflow_id})")
        
        # 4. 同步插件到数据库（创建 workflow_nodes 和 workflow_edges）
        syncer = PluginAutoSync(db)
        stats = syncer.sync_if_needed(workflow_id)
        print(f"✅ Plugin sync: {stats['added']} nodes, {stats['edges_created']} edges created")
        
        # 5. 初始化默认系统配置
        _init_default_system_configs(db)
        
    except Exception as e:
        print(f"❌ Init services failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


def _init_default_system_configs(db):
    """
    初始化默认系统配置
    使用 upsert 逻辑：不存在则创建，存在则跳过（不覆盖用户修改）
    """
    from langtrader_core.data.repositories.system_config import SystemConfigRepository
    
    # 默认配置列表（从现有数据库导出）
    DEFAULT_CONFIGS = [
        # ============ 缓存配置 ============
        {"config_key": "cache.ttl.tickers", "config_value": "10", "value_type": "integer", "category": "cache", "description": "行情数据缓存时间(秒)"},
        {"config_key": "cache.ttl.ohlcv_3m", "config_value": "300", "value_type": "integer", "category": "cache", "description": "3分钟K线缓存时间(秒)"},
        {"config_key": "cache.ttl.ohlcv_4h", "config_value": "3600", "value_type": "integer", "category": "cache", "description": "4小时K线缓存时间(秒)"},
        {"config_key": "cache.ttl.ohlcv", "config_value": "600", "value_type": "integer", "category": "cache", "description": "默认K线缓存时间(秒)"},
        {"config_key": "cache.ttl.orderbook", "config_value": "60", "value_type": "integer", "category": "cache", "description": "订单簿缓存时间(秒)"},
        {"config_key": "cache.ttl.trades", "config_value": "60", "value_type": "integer", "category": "cache", "description": "成交记录缓存时间(秒)"},
        {"config_key": "cache.ttl.markets", "config_value": "3600", "value_type": "integer", "category": "cache", "description": "市场信息缓存时间(秒)"},
        {"config_key": "cache.ttl.open_interests", "config_value": "600", "value_type": "integer", "category": "cache", "description": "持仓量缓存时间(秒)"},
        {"config_key": "cache.ttl.coin_selection", "config_value": "600", "value_type": "integer", "category": "cache", "description": "选币缓存时间(秒)"},
        {"config_key": "cache.ttl.backtest_ohlcv", "config_value": "604800", "value_type": "integer", "category": "cache", "description": "回测数据缓存时间(秒)", "is_editable": False},
        
        # ============ 交易配置 ============
        {"config_key": "trading.min_cycle_interval", "config_value": "60", "value_type": "integer", "category": "trading", "description": "最小交易周期(秒)"},
        {"config_key": "trading.max_concurrent_requests", "config_value": "10", "value_type": "integer", "category": "trading", "description": "API最大并发数"},
        {"config_key": "trading.default_timeframes", "config_value": '["3m", "4h"]', "value_type": "json", "category": "trading", "description": "默认时间框架"},
        {"config_key": "trading.default_ohlcv_limit", "config_value": "100", "value_type": "integer", "category": "trading", "description": "默认K线数据量"},
        
        # ============ API 限流配置 ============
        {"config_key": "api.rate_limit.binance", "config_value": "1200", "value_type": "integer", "category": "api", "description": "Binance API限制(/分钟)", "is_editable": False},
        {"config_key": "api.rate_limit.bybit", "config_value": "120", "value_type": "integer", "category": "api", "description": "Bybit API限制(/分钟)", "is_editable": False},
        {"config_key": "api.rate_limit.hyperliquid", "config_value": "600", "value_type": "integer", "category": "api", "description": "Hyperliquid API限制(/分钟)", "is_editable": False},
        {"config_key": "api.default_rate_limit", "config_value": "60", "value_type": "integer", "category": "api", "description": "未知交易所默认限制(/分钟)", "is_editable": False},
        
        # ============ 系统配置 ============
        {"config_key": "system.config_cache_ttl", "config_value": "60", "value_type": "integer", "category": "system", "description": "配置缓存时间(秒)"},
        {"config_key": "system.enable_hot_reload", "config_value": "true", "value_type": "boolean", "category": "system", "description": "是否启用配置热重载"},
        
        # ============ 辩论配置 ============
        {"config_key": "debate.enabled", "config_value": "true", "value_type": "boolean", "category": "debate", "description": "是否启用辩论机制"},
        {"config_key": "debate.max_rounds", "config_value": "2", "value_type": "integer", "category": "debate", "description": "最大辩论轮数"},
        {"config_key": "debate.consensus_threshold", "config_value": "2", "value_type": "integer", "category": "debate", "description": "达成共识所需的 approve 票数"},
        {"config_key": "debate.timeout_per_round", "config_value": "360", "value_type": "integer", "category": "debate", "description": "每轮辩论超时（秒）"},
        
        # ============ 批量决策配置 ============
        {"config_key": "batch_decision.max_total_allocation_pct", "config_value": "80.0", "value_type": "float", "category": "batch_decision", "description": "最大总仓位百分比"},
        {"config_key": "batch_decision.max_single_allocation_pct", "config_value": "40.0", "value_type": "float", "category": "batch_decision", "description": "单币种最大仓位百分比"},
        {"config_key": "batch_decision.min_cash_reserve_pct", "config_value": "20.0", "value_type": "float", "category": "batch_decision", "description": "最小现金储备百分比"},
        {"config_key": "batch_decision.timeout_seconds", "config_value": "360", "value_type": "integer", "category": "batch_decision", "description": "LLM 调用超时（秒）"},
        
        # ============ 辩论角色配置 ============
        {"config_key": "debate.roles", "config_value": '''[
    {"id": "risk_manager", "name": "风险经理", "name_en": "Risk Manager", "focus": "检查总仓位是否过高（应 <= 80%）；验证单币种仓位是否合理（应 <= 40%）；评估止损设置是否合理；识别高度相关的仓位（避免集中风险）；检查风险回报比（应 >= 2:1）", "style": "保守、谨慎、注重资本保护", "priority": 1},
    {"id": "portfolio_manager", "name": "组合经理", "name_en": "Portfolio Manager", "focus": "优化仓位分配比例；确保多样化，避免过度集中；评估币种之间的相关性；平衡风险与收益；考虑整体投资组合的夏普比率", "style": "平衡、全局视角、追求最优配比", "priority": 2},
    {"id": "contrarian", "name": "魔鬼代言人", "name_en": "Devil's Advocate", "focus": "挑战所有假设；找出决策中的漏洞；质疑过高的信心度；提出最坏情况场景；反驳过于乐观的判断", "style": "批判、追问、不轻易认同", "priority": 3}
]''', "value_type": "json", "category": "debate", "description": "辩论角色列表（JSON 数组）"},
    ]
    
    repo = SystemConfigRepository(db)
    created_count = 0
    
    for config in DEFAULT_CONFIGS:
        existing = repo.get_by_key(config["config_key"])
        if not existing:
            # 只创建不存在的配置，不覆盖已有配置
            repo.upsert(
                config_key=config["config_key"],
                config_value=config["config_value"],
                value_type=config.get("value_type", "string"),
                category=config.get("category"),
                description=config.get("description"),
                is_editable=config.get("is_editable", True),
            )
            created_count += 1
    
    if created_count > 0:
        print(f"✅ Created {created_count} default system configs")
    else:
        print(f"ℹ️ All {len(DEFAULT_CONFIGS)} default system configs already exist")


async def shutdown_services():
    """Cleanup services on application shutdown"""
    pass

