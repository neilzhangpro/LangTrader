# packages/langtrader_api/routes/v1/system_configs.py
"""
系统配置管理 API Routes
"""
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

from langtrader_api.dependencies import APIKey, DbSession
from langtrader_api.schemas.base import APIResponse
from langtrader_core.data.repositories.system_config import SystemConfigRepository
from langtrader_core.data.models.system_config import SystemConfigModel
from langtrader_core.services.config_manager import SystemConfig

router = APIRouter(prefix="/system-configs", tags=["System Configs"])


# ============ Pydantic Schemas ============

class SystemConfigCreate(BaseModel):
    """创建配置请求"""
    config_key: str
    config_value: str
    value_type: str = "string"  # string, integer, float, boolean, json
    category: Optional[str] = None  # cache, trading, api, system
    description: Optional[str] = None
    is_editable: bool = True


class SystemConfigUpdate(BaseModel):
    """更新配置请求"""
    config_value: Optional[str] = None
    value_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_editable: Optional[bool] = None


class SystemConfigResponse(BaseModel):
    """配置响应"""
    id: int
    config_key: str
    config_value: str
    value_type: str
    category: Optional[str]
    description: Optional[str]
    is_editable: bool
    updated_at: Optional[str]
    updated_by: Optional[str]

    class Config:
        from_attributes = True


class SystemConfigBulkCreate(BaseModel):
    """批量创建配置请求"""
    configs: List[SystemConfigCreate]


# ============ Helper Functions ============

def _model_to_response(config: SystemConfigModel) -> SystemConfigResponse:
    """将模型转换为响应"""
    return SystemConfigResponse(
        id=config.id,
        config_key=config.config_key,
        config_value=config.config_value,
        value_type=config.value_type or "string",
        category=config.category,
        description=config.description,
        is_editable=config.is_editable if config.is_editable is not None else True,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
        updated_by=config.updated_by,
    )


# ============ API Endpoints ============

@router.get("", response_model=APIResponse[List[SystemConfigResponse]])
async def list_system_configs(
    api_key: APIKey,
    db: DbSession,
    category: Optional[str] = Query(None, description="按类别过滤"),
    prefix: Optional[str] = Query(None, description="按 key 前缀过滤"),
):
    """
    获取所有系统配置
    
    支持按 category 或 key 前缀过滤
    """
    repo = SystemConfigRepository(db)
    
    if prefix:
        configs = repo.get_by_prefix(prefix)
    else:
        configs = repo.get_all(category=category)
    
    result = [_model_to_response(c) for c in configs]
    return APIResponse(data=result)


@router.get("/categories", response_model=APIResponse[List[str]])
async def list_categories(
    api_key: APIKey,
    db: DbSession,
):
    """获取所有配置类别"""
    repo = SystemConfigRepository(db)
    categories = repo.get_categories()
    return APIResponse(data=categories)


@router.get("/{config_id}", response_model=APIResponse[SystemConfigResponse])
async def get_system_config(
    config_id: int,
    api_key: APIKey,
    db: DbSession,
):
    """获取单个系统配置"""
    repo = SystemConfigRepository(db)
    config = repo.get_by_id(config_id)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config with id {config_id} not found"
        )
    
    return APIResponse(data=_model_to_response(config))


@router.get("/key/{config_key:path}", response_model=APIResponse[SystemConfigResponse])
async def get_system_config_by_key(
    config_key: str,
    api_key: APIKey,
    db: DbSession,
):
    """
    通过 key 获取系统配置
    
    key 使用点分隔命名空间，如 cache.ttl.tickers
    """
    repo = SystemConfigRepository(db)
    config = repo.get_by_key(config_key)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config with key '{config_key}' not found"
        )
    
    return APIResponse(data=_model_to_response(config))


@router.post("", response_model=APIResponse[SystemConfigResponse], status_code=status.HTTP_201_CREATED)
async def create_system_config(
    request: SystemConfigCreate,
    api_key: APIKey,
    db: DbSession,
):
    """创建系统配置"""
    repo = SystemConfigRepository(db)
    
    # 检查 key 是否已存在
    existing = repo.get_by_key(request.config_key)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Config key '{request.config_key}' already exists"
        )
    
    config = SystemConfigModel(
        config_key=request.config_key,
        config_value=request.config_value,
        value_type=request.value_type,
        category=request.category,
        description=request.description,
        is_editable=request.is_editable,
        updated_at=datetime.now(),
    )
    
    config = repo.create(config)
    
    # 刷新缓存
    SystemConfig.reload(db)
    
    return APIResponse(data=_model_to_response(config))


@router.post("/bulk", response_model=APIResponse[List[SystemConfigResponse]], status_code=status.HTTP_201_CREATED)
async def bulk_create_system_configs(
    request: SystemConfigBulkCreate,
    api_key: APIKey,
    db: DbSession,
):
    """
    批量创建或更新系统配置（upsert）
    
    如果 key 已存在则更新，否则创建
    """
    repo = SystemConfigRepository(db)
    results = []
    
    for item in request.configs:
        config = repo.upsert(
            config_key=item.config_key,
            config_value=item.config_value,
            value_type=item.value_type,
            category=item.category,
            description=item.description,
            is_editable=item.is_editable,
        )
        results.append(_model_to_response(config))
    
    # 刷新缓存
    SystemConfig.reload(db)
    
    return APIResponse(data=results)


@router.put("/{config_id}", response_model=APIResponse[SystemConfigResponse])
async def update_system_config(
    config_id: int,
    request: SystemConfigUpdate,
    api_key: APIKey,
    db: DbSession,
):
    """更新系统配置"""
    repo = SystemConfigRepository(db)
    
    config = repo.get_by_id(config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config with id {config_id} not found"
        )
    
    if not config.is_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Config '{config.config_key}' is not editable"
        )
    
    updates = request.model_dump(exclude_unset=True)
    config = repo.update(config_id, updates)
    
    # 刷新缓存
    SystemConfig.reload(db)
    
    return APIResponse(data=_model_to_response(config))


@router.delete("/{config_id}", response_model=APIResponse[dict])
async def delete_system_config(
    config_id: int,
    api_key: APIKey,
    db: DbSession,
):
    """删除系统配置"""
    repo = SystemConfigRepository(db)
    
    config = repo.get_by_id(config_id)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config with id {config_id} not found"
        )
    
    if not config.is_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Config '{config.config_key}' is not editable"
        )
    
    key = config.config_key
    repo.delete(config_id)
    
    # 刷新缓存
    SystemConfig.reload(db)
    
    return APIResponse(data={"message": f"Config '{key}' deleted"})


@router.delete("/key/{config_key:path}", response_model=APIResponse[dict])
async def delete_system_config_by_key(
    config_key: str,
    api_key: APIKey,
    db: DbSession,
):
    """通过 key 删除系统配置"""
    repo = SystemConfigRepository(db)
    
    config = repo.get_by_key(config_key)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config with key '{config_key}' not found"
        )
    
    if not config.is_editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Config '{config.config_key}' is not editable"
        )
    
    repo.delete_by_key(config_key)
    
    # 刷新缓存
    SystemConfig.reload(db)
    
    return APIResponse(data={"message": f"Config '{config_key}' deleted"})

