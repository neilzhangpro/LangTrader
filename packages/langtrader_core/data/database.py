# packages/langtrader_core/data/database.py
import os

from sqlmodel import create_engine, SQLModel, Session
from typing import Generator
from dotenv import load_dotenv
load_dotenv()
from langgraph.checkpoint.postgres import PostgresSaver

# 使用同步驱动
database_url = os.getenv("DATABASE_URL")
engine = create_engine(database_url, echo=False)

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

