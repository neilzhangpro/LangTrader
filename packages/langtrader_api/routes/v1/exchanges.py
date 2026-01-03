"""
Exchange 管理 API Routes

交易所配置的 CRUD 操作，包括：
- 列表查询
- 详情查看
- 创建/更新/删除
- 连接测试
- 余额查询
"""
from fastapi import APIRouter, HTTPException, status
from typing import Optional
from datetime import datetime

from langtrader_api.dependencies import APIKey, ExchangeRepo, DbSession
from langtrader_api.schemas.base import APIResponse, PaginatedResponse
from langtrader_api.schemas.exchanges import (
    ExchangeSummary, ExchangeDetail, ExchangeCreateRequest, 
    ExchangeUpdateRequest, ExchangeBalance, ExchangeTestResult
)
from langtrader_core.data.models.exchange import exchange as Exchange

router = APIRouter(prefix="/exchanges", tags=["Exchanges"])


# =============================================================================
# List & Get
# =============================================================================

@router.get("", response_model=APIResponse[list])
async def list_exchanges(
    api_key: APIKey,
    exchange_repo: ExchangeRepo,
):
    """
    获取所有交易所配置列表
    
    注意：API Key 和 Secret Key 会被脱敏显示
    """
    exchanges = exchange_repo.get_all()
    
    # 脱敏处理
    result = []
    for ex in exchanges:
        result.append(ExchangeSummary(
            id=ex['id'],
            name=ex['name'],
            type=ex['type'],
            testnet=ex.get('testnet', False),
            has_api_key=bool(ex.get('apikey')),
            has_secret_key=bool(ex.get('secretkey')),
        ))
    
    return APIResponse(data=result)


@router.get("/{exchange_id}", response_model=APIResponse[ExchangeDetail])
async def get_exchange(
    exchange_id: int,
    api_key: APIKey,
    exchange_repo: ExchangeRepo,
):
    """
    获取交易所详情
    
    API Key 会部分脱敏显示（显示前4位和后4位）
    """
    ex = exchange_repo.get_by_id(exchange_id)
    if not ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exchange with id {exchange_id} not found"
        )
    
    # 脱敏 API Key
    def mask_key(key: str) -> str:
        if not key or len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"
    
    return APIResponse(data=ExchangeDetail(
        id=ex['id'],
        name=ex['name'],
        type=ex['type'],
        testnet=ex.get('testnet', False),
        apikey_masked=mask_key(ex.get('apikey', '')),
        has_uid=bool(ex.get('uid')),
        has_password=bool(ex.get('password')),
        slippage=ex.get('slippage'),
    ))


# =============================================================================
# Create & Update
# =============================================================================

@router.post("", response_model=APIResponse[ExchangeDetail], status_code=status.HTTP_201_CREATED)
async def create_exchange(
    request: ExchangeCreateRequest,
    api_key: APIKey,
    exchange_repo: ExchangeRepo,
    db: DbSession,
):
    """
    创建新的交易所配置
    
    支持的交易所类型：binance, hyperliquid, okx, bybit 等
    """
    # 创建交易所对象
    ex = Exchange(
        name=request.name,
        type=request.type,
        apikey=request.apikey,
        secretkey=request.secretkey,
        uid=request.uid,
        password=request.password,
        testnet=request.testnet,
        slippage=request.slippage,
    )
    
    db.add(ex)
    db.commit()
    db.refresh(ex)
    
    # 脱敏返回
    def mask_key(key: str) -> str:
        if not key or len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"
    
    return APIResponse(
        data=ExchangeDetail(
            id=ex.id,
            name=ex.name,
            type=ex.type,
            testnet=ex.testnet,
            apikey_masked=mask_key(ex.apikey),
            has_uid=bool(ex.uid),
            has_password=bool(ex.password),
            slippage=ex.slippage,
        ),
        message=f"Exchange '{ex.name}' created successfully"
    )


@router.patch("/{exchange_id}", response_model=APIResponse[ExchangeDetail])
async def update_exchange(
    exchange_id: int,
    request: ExchangeUpdateRequest,
    api_key: APIKey,
    exchange_repo: ExchangeRepo,
    db: DbSession,
):
    """
    更新交易所配置
    
    只更新提供的字段，未提供的字段保持不变
    """
    # 获取原始数据
    ex_data = exchange_repo.get_by_id(exchange_id)
    if not ex_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exchange with id {exchange_id} not found"
        )
    
    # 获取 ORM 对象
    from sqlmodel import select
    stmt = select(Exchange).where(Exchange.id == exchange_id)
    ex = db.exec(stmt).first()
    
    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ex, field, value)
    
    db.add(ex)
    db.commit()
    db.refresh(ex)
    
    # 脱敏返回
    def mask_key(key: str) -> str:
        if not key or len(key) < 8:
            return "***"
        return f"{key[:4]}...{key[-4:]}"
    
    return APIResponse(
        data=ExchangeDetail(
            id=ex.id,
            name=ex.name,
            type=ex.type,
            testnet=ex.testnet,
            apikey_masked=mask_key(ex.apikey),
            has_uid=bool(ex.uid),
            has_password=bool(ex.password),
            slippage=ex.slippage,
        ),
        message=f"Exchange '{ex.name}' updated successfully"
    )


@router.delete("/{exchange_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exchange(
    exchange_id: int,
    api_key: APIKey,
    exchange_repo: ExchangeRepo,
):
    """
    删除交易所配置
    
    警告：删除后无法恢复，关联的 Bot 将无法正常运行
    """
    ex = exchange_repo.get_by_id(exchange_id)
    if not ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exchange with id {exchange_id} not found"
        )
    
    exchange_repo.delete(exchange_id)


# =============================================================================
# Test & Balance
# =============================================================================

@router.post("/{exchange_id}/test", response_model=APIResponse[ExchangeTestResult])
async def test_exchange_connection(
    exchange_id: int,
    api_key: APIKey,
    exchange_repo: ExchangeRepo,
):
    """
    测试交易所连接
    
    验证 API Key 是否有效，返回连接状态
    """
    ex = exchange_repo.get_by_id(exchange_id)
    if not ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exchange with id {exchange_id} not found"
        )
    
    try:
        import ccxt
        
        # 创建 ccxt 交易所实例
        exchange_class = getattr(ccxt, ex['type'], None)
        if not exchange_class:
            return APIResponse(
                data=ExchangeTestResult(
                    success=False,
                    message=f"Unsupported exchange type: {ex['type']}",
                    latency_ms=None,
                )
            )
        
        config = {
            'apiKey': ex['apikey'],
            'secret': ex['secretkey'],
        }
        
        if ex.get('uid'):
            config['uid'] = ex['uid']
        if ex.get('password'):
            config['password'] = ex['password']
        if ex.get('testnet'):
            config['sandbox'] = True
        
        exchange_instance = exchange_class(config)
        
        # 测试连接
        import time
        start = time.time()
        exchange_instance.fetch_time()
        latency = int((time.time() - start) * 1000)
        
        return APIResponse(
            data=ExchangeTestResult(
                success=True,
                message="Connection successful",
                latency_ms=latency,
            )
        )
        
    except Exception as e:
        return APIResponse(
            data=ExchangeTestResult(
                success=False,
                message=str(e),
                latency_ms=None,
            )
        )


@router.get("/{exchange_id}/balance", response_model=APIResponse[ExchangeBalance])
async def get_exchange_balance(
    exchange_id: int,
    api_key: APIKey,
    exchange_repo: ExchangeRepo,
):
    """
    获取交易所账户余额
    
    返回 USDT/USDC 等稳定币余额
    """
    ex = exchange_repo.get_by_id(exchange_id)
    if not ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exchange with id {exchange_id} not found"
        )
    
    try:
        import ccxt
        
        # 创建 ccxt 交易所实例
        exchange_class = getattr(ccxt, ex['type'], None)
        if not exchange_class:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported exchange type: {ex['type']}"
            )
        
        config = {
            'apiKey': ex['apikey'],
            'secret': ex['secretkey'],
        }
        
        if ex.get('uid'):
            config['uid'] = ex['uid']
        if ex.get('password'):
            config['password'] = ex['password']
        if ex.get('testnet'):
            config['sandbox'] = True
        
        exchange_instance = exchange_class(config)
        
        # 获取余额
        balance = exchange_instance.fetch_balance()
        
        # 提取主要币种余额
        total_usd = 0.0
        balances = {}
        
        for currency in ['USDT', 'USDC', 'USD', 'BUSD']:
            if currency in balance.get('total', {}):
                amount = float(balance['total'][currency] or 0)
                if amount > 0:
                    balances[currency] = amount
                    total_usd += amount
        
        return APIResponse(
            data=ExchangeBalance(
                exchange_id=exchange_id,
                exchange_name=ex['name'],
                total_usd=total_usd,
                balances=balances,
                updated_at=datetime.now(),
            )
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch balance: {str(e)}"
        )

