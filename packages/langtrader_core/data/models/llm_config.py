# packages/langtrader_core/data/models/llm_config.py
"""
LLM 配置模型

重试机制说明：
- LangChain 内置支持 max_retries 参数
- 参考: https://docs.langchain.com/oss/python/langchain/models#parameters
- ChatOpenAI/ChatAnthropic 等模型都支持此参数
- 当 API 调用失败时，SDK 会自动重试指定次数
- 无需自定义重试装饰器或熔断器
"""

from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


class LLMConfig(SQLModel, table=True):
    """
    LLM 配置模型
    统一管理所有 LLM 提供者和模型配置
    
    重试机制：
    - max_retries 参数会传递给 LangChain 模型
    - LangChain 会自动处理 API 调用失败的重试
    - 默认重试 3 次，可在数据库中配置
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