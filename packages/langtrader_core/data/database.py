# packages/langtrader_core/data/database.py
"""
数据库连接管理

配置 SQLAlchemy 连接池以支持高并发场景。
"""
import os

from sqlmodel import create_engine, SQLModel, Session
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

def init_db():
    """
    initialize the database tables
    """
    SQLModel.metadata.create_all(engine)
    # when database initialized setup up checkpointer
    print(f"🔧 Initializing LangGraph checkpointer schema...")
    with PostgresSaver.from_conn_string(database_url) as checkpointer:
        checkpointer.setup()

def get_session() -> Generator[Session, None, None]:
    """
    get the database session
    """
    with Session(engine) as session:
        yield session

def SessionLocal() -> Session:
    """
    Create a new database session
    """
    return Session(engine)

