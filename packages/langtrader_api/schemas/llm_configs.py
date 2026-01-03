"""
LLM Config API Schemas

LLM 配置相关的请求和响应模型
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal


# =============================================================================
# Response Models
# =============================================================================

class LLMConfigSummary(BaseModel):
    """LLM 配置列表项（简要信息）"""
    id: int
    name: str
    display_name: Optional[str] = None
    provider: str  # openai, anthropic, azure, ollama, custom
    model_name: str
    is_enabled: bool = True
    is_default: bool = False


class LLMConfigDetail(BaseModel):
    """LLM 配置详情"""
    id: int
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    provider: str
    model_name: str
    base_url: Optional[str] = None
    api_key_masked: Optional[str] = None  # 脱敏后的 API Key
    temperature: float = 0.7
    max_retries: int = 3
    is_enabled: bool = True
    is_default: bool = False
    created_at: datetime
    updated_at: datetime


class LLMConfigTestResult(BaseModel):
    """LLM 连接测试结果"""
    success: bool
    message: str
    response_preview: Optional[str] = None  # 测试响应预览
    latency_ms: Optional[int] = None


# =============================================================================
# Request Models
# =============================================================================

class LLMConfigCreateRequest(BaseModel):
    """创建 LLM 配置请求"""
    name: str = Field(..., min_length=1, max_length=255, description="配置名称（唯一）")
    display_name: Optional[str] = Field(None, max_length=255, description="显示名称")
    description: Optional[str] = Field(None, description="配置描述")
    
    provider: str = Field(
        default="openai",
        description="LLM 提供者：openai, anthropic, azure, ollama, custom"
    )
    model_name: str = Field(..., description="模型名称，如 gpt-4o-mini, claude-3-5-sonnet")
    base_url: Optional[str] = Field(None, description="自定义 API 端点（用于代理或自托管）")
    api_key: Optional[str] = Field(None, description="API 密钥")
    
    temperature: Decimal = Field(
        default=Decimal("0.70"),
        ge=0,
        le=2,
        description="温度参数（0-2）"
    )
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    
    is_enabled: bool = Field(default=True, description="是否启用")


class LLMConfigUpdateRequest(BaseModel):
    """更新 LLM 配置请求（所有字段可选）"""
    display_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    
    provider: Optional[str] = None
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    
    temperature: Optional[Decimal] = Field(None, ge=0, le=2)
    max_retries: Optional[int] = Field(None, ge=0, le=10)
    
    is_enabled: Optional[bool] = None

