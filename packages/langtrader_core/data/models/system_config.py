# packages/langtrader_core/data/models/system_config.py
"""
系统配置模型
"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime


class SystemConfigModel(SQLModel, table=True):
    """
    系统全局配置
    
    config_key 使用点分隔命名空间，例如：
    - cache.ttl.tickers
    - trading.default_leverage
    - api.rate_limit
    """
    __tablename__ = "system_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    config_key: str = Field(unique=True, index=True, max_length=100)
    config_value: str
    value_type: str = Field(default="string", max_length=50)  # string, integer, float, boolean, json
    category: Optional[str] = Field(default=None, max_length=50)  # cache, trading, api, system
    description: Optional[str] = None
    is_editable: bool = Field(default=True)
    updated_at: Optional[datetime] = Field(default_factory=datetime.now)
    updated_by: Optional[str] = Field(default=None, max_length=100)

