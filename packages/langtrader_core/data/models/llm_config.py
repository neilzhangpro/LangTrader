# packages/langtrader_core/data/models/llm_config.py

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class LLMConfig(SQLModel, table=True):
    """
    LLM 配置模型
    统一管理所有 LLM 提供者和模型配置
    """
    __tablename__ = "llm_configs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 基本信息
    name: str = Field(unique=True, index=True)
    display_name: Optional[str] = None
    description: Optional[str] = None
    
    # LLM 配置
    provider: str = Field(default="openai")  # openai, anthropic, azure, ollama, custom
    model_name: str = Field()  # gpt-4o-mini, claude-3-5-sonnet, etc.
    base_url: Optional[str] = None  # 自定义 API 端点
    api_key: Optional[str] = None  # API 密钥
    
    # 模型参数
    temperature: Decimal = Field(default=Decimal("0.70"))
    max_retries: int = Field(default=3)
    
    # 状态管理
    is_enabled: bool = Field(default=True)
    is_default: bool = Field(default=False)
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[str] = None
    
    def to_langchain_kwargs(self) -> dict:
        """
        转换为 LangChain 初始化参数
        """
        kwargs = {
            "model": self.model_name,
            "temperature": float(self.temperature),
            "max_retries": self.max_retries,
        }
        
        if self.base_url:
            kwargs["base_url"] = self.base_url
        
        if self.api_key:
            kwargs["api_key"] = self.api_key
        
        return kwargs