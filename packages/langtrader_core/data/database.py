# packages/langtrader_core/data/database.py
"""
数据库连接管理

配置 SQLAlchemy 连接池以支持高并发场景。
"""
import os

from sqlmodel import create_engine, SQLModel, Session
from sqlalchemy import text
from typing import Generator
from dotenv import load_dotenv
load_dotenv()
from langgraph.checkpoint.postgres import PostgresSaver

# 使用同步驱动
database_url = os.getenv("DATABASE_URL")

# 配置连接池参数
engine = create_engine(
    database_url,
    echo=False,
    pool_size=10,          # 连接池大小
    max_overflow=20,       # 超出 pool_size 后可创建的最大连接数
    pool_pre_ping=True,    # 连接健康检查，防止使用已断开的连接
    pool_recycle=3600,     # 连接回收时间（秒），防止长连接问题
)


def _init_system_configs():
    """
    初始化 system_configs 表和默认配置
    
    在数据库初始化时自动创建配置表并插入默认值。
    使用 ON CONFLICT DO NOTHING 确保幂等性。
    """
    # 创建 system_configs 表
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS system_configs (
        id SERIAL PRIMARY KEY,
        config_key VARCHAR(100) UNIQUE NOT NULL,
        config_value TEXT NOT NULL,
        value_type VARCHAR(50) DEFAULT 'string',
        category VARCHAR(50),
        description TEXT,
        is_editable BOOLEAN DEFAULT true,
        updated_at TIMESTAMP DEFAULT NOW(),
        updated_by VARCHAR(100)
    );
    CREATE INDEX IF NOT EXISTS idx_system_configs_category ON system_configs(category);
    CREATE INDEX IF NOT EXISTS idx_system_configs_key ON system_configs(config_key);
    """
    
    # 默认配置列表：(config_key, config_value, value_type, category, description, is_editable)
    default_configs = [
        # ========== 缓存配置 ==========
        ('cache.ttl.tickers', '10', 'integer', 'cache', '行情数据缓存时间(秒)', True),
        ('cache.ttl.ohlcv_3m', '300', 'integer', 'cache', '3分钟K线缓存时间(秒)', True),
        ('cache.ttl.ohlcv_4h', '3600', 'integer', 'cache', '4小时K线缓存时间(秒)', True),
        ('cache.ttl.ohlcv', '600', 'integer', 'cache', '默认K线缓存时间(秒)', True),
        ('cache.ttl.orderbook', '60', 'integer', 'cache', '订单簿缓存时间(秒)', True),
        ('cache.ttl.trades', '60', 'integer', 'cache', '成交记录缓存时间(秒)', True),
        ('cache.ttl.markets', '3600', 'integer', 'cache', '市场信息缓存时间(秒)', True),
        ('cache.ttl.open_interests', '600', 'integer', 'cache', '持仓量缓存时间(秒)', True),
        ('cache.ttl.coin_selection', '600', 'integer', 'cache', '选币缓存时间(秒)', True),
        ('cache.ttl.backtest_ohlcv', '604800', 'integer', 'cache', '回测数据缓存时间(秒)', False),
        
        # ========== 交易配置 ==========
        ('trading.min_cycle_interval', '60', 'integer', 'trading', '最小交易周期(秒)', True),
        ('trading.max_concurrent_requests', '10', 'integer', 'trading', 'API最大并发数', True),
        ('trading.default_timeframes', '["3m", "4h"]', 'json', 'trading', '默认时间框架', True),
        ('trading.default_ohlcv_limit', '100', 'integer', 'trading', '默认K线数据量', True),
        
        # ========== API 限制配置 ==========
        ('api.rate_limit.binance', '1200', 'integer', 'api', 'Binance API限制(/分钟)', False),
        ('api.rate_limit.bybit', '120', 'integer', 'api', 'Bybit API限制(/分钟)', False),
        ('api.rate_limit.hyperliquid', '600', 'integer', 'api', 'Hyperliquid API限制(/分钟)', False),
        ('api.default_rate_limit', '60', 'integer', 'api', '未知交易所默认限制(/分钟)', False),
        
        # ========== 系统配置 ==========
        ('system.config_cache_ttl', '60', 'integer', 'system', '配置缓存时间(秒)', True),
        ('system.enable_hot_reload', 'true', 'boolean', 'system', '是否启用配置热重载', True),
        
        # ========== 辩论配置 ==========
        ('debate.enabled', 'true', 'boolean', 'debate', '是否启用辩论模式', True),
        ('debate.rounds', '3', 'integer', 'debate', '辩论回合数', True),
        ('debate.timeout_per_phase', '120', 'integer', 'debate', '每阶段超时(秒)', True),
        
        # ========== 市场状态识别配置 ==========
        ('market_regime.adx_trending_threshold', '25', 'integer', 'market_regime', 'ADX 趋势阈值，超过此值视为趋势市', True),
        ('market_regime.bb_width_ranging_threshold', '0.03', 'float', 'market_regime', 'BB 宽度震荡阈值（小数），低于此值视为窄幅震荡', True),
        ('market_regime.bb_width_volatile_threshold', '0.08', 'float', 'market_regime', 'BB 宽度高波动阈值（小数），超过此值视为高波动', True),
        ('market_regime.continue_if_has_positions', 'true', 'boolean', 'market_regime', '有持仓时是否继续进入决策以管理持仓', True),
        ('market_regime.primary_timeframe', '4h', 'string', 'market_regime', '市场状态判断主要参考的时间框架', True),
    ]
    
    with engine.connect() as conn:
        try:
            # 创建表
            conn.execute(text(create_table_sql))
            conn.commit()
            
            # 插入默认配置
            insert_sql = """
            INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable)
            VALUES (:key, :value, :type, :category, :description, :editable)
            ON CONFLICT (config_key) DO NOTHING
            """
            for config in default_configs:
                conn.execute(text(insert_sql), {
                    'key': config[0],
                    'value': config[1],
                    'type': config[2],
                    'category': config[3],
                    'description': config[4],
                    'editable': config[5],
                })
            conn.commit()
            print(f"✅ System configs initialized ({len(default_configs)} configs)")
        except Exception as e:
            print(f"⚠️ System configs initialization warning: {e}")


def _migrate_schema():
    """
    自动添加/修复数据库 schema（向后兼容）
    
    - 添加新列（使用 IF NOT EXISTS 确保幂等性）
    - 修复 NOT NULL 约束（模型允许 NULL 但数据库不允许的情况）
    - 新用户：create_all 会创建完整表，这些修改会被跳过
    - 老用户：自动补齐缺失的列和修复约束
    """
    migrations = [
        # ========== workflows 表 ==========
        "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
        "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS tags TEXT[]",
        "ALTER TABLE workflows ADD COLUMN IF NOT EXISTS created_by VARCHAR(255)",
        
        # ========== workflow_nodes 表 ==========
        "ALTER TABLE workflow_nodes ADD COLUMN IF NOT EXISTS display_name VARCHAR(255)",
        "ALTER TABLE workflow_nodes ADD COLUMN IF NOT EXISTS description TEXT",
        
        # ========== bots 表：修复 NOT NULL 约束 ==========
        # 这些字段在模型中是 Optional 或 default=None，但老数据库有 NOT NULL 约束
        "ALTER TABLE bots ALTER COLUMN tracing_key DROP NOT NULL",
        "ALTER TABLE bots ALTER COLUMN prompt DROP NOT NULL",
        "ALTER TABLE bots ALTER COLUMN tavily_search_key DROP NOT NULL",
        "ALTER TABLE bots ALTER COLUMN llm_id DROP NOT NULL",
        # 设置合理的默认值（如果没有的话）
        "ALTER TABLE bots ALTER COLUMN prompt SET DEFAULT 'default.txt'",
        
        # ========== bots 表：添加新字段 ==========
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS max_leverage INTEGER DEFAULT 3",
        "ALTER TABLE bots ADD COLUMN IF NOT EXISTS max_concurrent_symbols INTEGER DEFAULT 5",
    ]
    
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                # 忽略常见的无害错误
                error_msg = str(e).lower()
                if any(x in error_msg for x in [
                    "does not exist",      # 表/列不存在（首次启动）
                    "already exists",      # 列已存在
                    "is not present",      # 约束不存在
                    "no such constraint",  # 约束不存在
                ]):
                    pass
                else:
                    print(f"⚠️ Migration warning: {e}")


def init_db():
    """
    初始化数据库表结构
    
    流程：
    1. 创建所有表（新表会完整创建，已存在的表不变）
    2. 运行迁移脚本（为已存在的表添加缺失的列）
    3. 初始化 system_configs 表和默认配置
    4. 初始化 LangGraph checkpointer（仅在表不存在时，使用 advisory lock 防止并发冲突）
    
    注意：多个 bot 可以并发调用此函数，使用 PostgreSQL advisory lock 避免 DDL 操作的并发冲突。
    """
    # 🚀 快速路径：如果核心表已存在，跳过 DDL 操作（但仍初始化配置）
    # 这避免了多进程同时调用时的锁竞争
    try:
        with engine.connect() as conn:
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'bots')"
            ))
            bots_exists = result.scalar()
            
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoints')"
            ))
            checkpoints_exists = result.scalar()
            
            if bots_exists and checkpoints_exists:
                print(f"✅ Database already initialized, skipping DDL operations")
                # 仍然初始化 system_configs（使用 ON CONFLICT DO NOTHING 确保幂等性）
                _init_system_configs()
                return
    except Exception as e:
        print(f"⚠️ Quick check failed, proceeding with full init: {e}")
    
    # 1. 创建表结构
    SQLModel.metadata.create_all(engine)
    
    # 2. 自动迁移：添加缺失的列（兼容老数据库）
    _migrate_schema()
    
    # 3. 初始化 system_configs 表和默认配置
    _init_system_configs()
    
    # 4. LangGraph checkpointer - 使用 advisory lock 确保只有一个进程执行 setup()
    # Advisory lock key: 使用固定的大整数作为锁标识
    CHECKPOINTER_LOCK_KEY = 20250107  # 固定的锁 ID
    
    print(f"🔧 Checking LangGraph checkpointer schema...")
    try:
        with engine.connect() as conn:
            # 首次检查表是否存在（快速路径，避免不必要的锁获取）
            result = conn.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoints')"
            ))
            table_exists = result.scalar()
            
            if table_exists:
                print(f"✅ LangGraph checkpointer tables already exist")
                return
            
            # 表不存在，尝试获取 advisory lock（非阻塞模式）
            print(f"🔒 Attempting to acquire advisory lock for checkpointer setup...")
            lock_result = conn.execute(text(
                f"SELECT pg_try_advisory_lock({CHECKPOINTER_LOCK_KEY})"
            ))
            got_lock = lock_result.scalar()
            
            if got_lock:
                try:
                    # 双重检查：获取锁后再次确认表不存在
                    result = conn.execute(text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoints')"
                    ))
                    table_exists = result.scalar()
                    
                    if not table_exists:
                        print(f"🔧 Creating LangGraph checkpointer tables...")
                        with PostgresSaver.from_conn_string(database_url) as checkpointer:
                            checkpointer.setup()
                        print(f"✅ LangGraph checkpointer initialized")
                    else:
                        print(f"✅ LangGraph checkpointer tables created by another process")
                finally:
                    # 释放 advisory lock
                    conn.execute(text(f"SELECT pg_advisory_unlock({CHECKPOINTER_LOCK_KEY})"))
                    conn.commit()
            else:
                # 未获取到锁，说明另一个进程正在创建表，等待表创建完成
                print(f"⏳ Another process is creating checkpointer tables, waiting...")
                
                # 等待表创建完成（最多等待 30 秒）
                max_wait = 30
                wait_interval = 0.5
                waited = 0
                
                while waited < max_wait:
                    import time
                    time.sleep(wait_interval)
                    waited += wait_interval
                    
                    result = conn.execute(text(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'checkpoints')"
                    ))
                    if result.scalar():
                        print(f"✅ LangGraph checkpointer tables ready (waited {waited:.1f}s)")
                        return
                
                print(f"⚠️ Timeout waiting for checkpointer tables, continuing anyway...")
    
    except Exception as e:
        # 如果检查失败，打印警告但不阻塞启动
        print(f"⚠️ LangGraph checkpointer check failed: {e}")


def get_session() -> Generator[Session, None, None]:
    """获取数据库 session"""
    with Session(engine) as session:
        yield session


def SessionLocal() -> Session:
    """创建新的数据库 session"""
    return Session(engine)

