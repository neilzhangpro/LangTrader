"""
Exchange API Schemas

交易所配置相关的请求和响应模型
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime


# =============================================================================
# Response Models
# =============================================================================

class ExchangeSummary(BaseModel):
    """交易所列表项（简要信息）"""
    id: int
    name: str
    type: str  # binance, hyperliquid, okx, bybit
    testnet: bool = False
    has_api_key: bool = False
    has_secret_key: bool = False


class ExchangeDetail(BaseModel):
    """交易所详情（包含脱敏的密钥信息）"""
    id: int
    name: str
    type: str
    testnet: bool = False
    apikey_masked: str = "***"  # 脱敏后的 API Key
    has_uid: bool = False
    has_password: bool = False
    slippage: Optional[float] = None


class ExchangeTestResult(BaseModel):
    """交易所连接测试结果"""
    success: bool
    message: str
    latency_ms: Optional[int] = None


class ExchangeBalance(BaseModel):
    """交易所账户余额"""
    exchange_id: int
    exchange_name: str
    total_usd: float = 0.0
    balances: Dict[str, float] = Field(default_factory=dict)  # {USDT: 1000, USDC: 500}
    updated_at: datetime


# =============================================================================
# Request Models
# =============================================================================

class ExchangeCreateRequest(BaseModel):
    """创建交易所请求"""
    name: str = Field(..., min_length=1, max_length=255, description="交易所配置名称")
    type: str = Field(..., description="交易所类型：binance, hyperliquid, okx, bybit 等")
    apikey: str = Field(..., min_length=1, description="API Key")
    secretkey: str = Field(..., min_length=1, description="Secret Key")
    uid: Optional[str] = Field(None, description="UID（某些交易所需要）")
    password: Optional[str] = Field(None, description="交易密码（某些交易所需要）")
    testnet: bool = Field(default=False, description="是否使用测试网")
    slippage: Optional[float] = Field(None, ge=0, le=0.1, description="滑点设置（0-0.1）")


class ExchangeUpdateRequest(BaseModel):
    """更新交易所请求（所有字段可选）"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = None
    apikey: Optional[str] = None
    secretkey: Optional[str] = None
    uid: Optional[str] = None
    password: Optional[str] = None
    testnet: Optional[bool] = None
    slippage: Optional[float] = Field(None, ge=0, le=0.1)

