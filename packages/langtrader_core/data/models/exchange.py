# packages/langtrader_core/data/models/exchange.py
"""
交易所配置模型
"""
from sqlmodel import SQLModel, Field
from typing import Optional


class exchange(SQLModel, table=True):
    """交易所配置模型"""
    __tablename__ = "exchanges"

    id: int = Field(default=None, primary_key=True)
    type: str
    name: str
    apikey: str
    secretkey: str
    uid: Optional[str] = None
    password: Optional[str] = None
    testnet: bool = False
    IoTop: bool = False
    slippage: Optional[float] = None 
    