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
    3. 初始化 LangGraph checkpointer（仅在表不存在时，使用 advisory lock 防止并发冲突）
    
    注意：多个 bot 可以并发调用此函数，使用 PostgreSQL advisory lock 避免 DDL 操作的并发冲突。
    """
    # 🚀 快速路径：如果核心表已存在，跳过所有 DDL 操作
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
                return
    except Exception as e:
        print(f"⚠️ Quick check failed, proceeding with full init: {e}")
    
    # 1. 创建表结构
    SQLModel.metadata.create_all(engine)
    
    # 2. 自动迁移：添加缺失的列（兼容老数据库）
    _migrate_schema()
    
    # 3. LangGraph checkpointer - 使用 advisory lock 确保只有一个进程执行 setup()
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

