"""
LLM Config 管理 API Routes

LLM 配置的 CRUD 操作，包括：
- 列表查询
- 详情查看
- 创建/更新/删除
- 设置默认配置
- 连接测试
"""
from fastapi import APIRouter, HTTPException, status
from typing import Optional
from datetime import datetime

from langtrader_api.dependencies import APIKey, LLMConfigRepo, DbSession
from langtrader_api.schemas.base import APIResponse
from langtrader_api.schemas.llm_configs import (
    LLMConfigSummary, LLMConfigDetail, LLMConfigCreateRequest,
    LLMConfigUpdateRequest, LLMConfigTestResult
)
from langtrader_core.data.models.llm_config import LLMConfig

router = APIRouter(prefix="/llm-configs", tags=["LLM Configs"])


# =============================================================================
# List & Get
# =============================================================================

@router.get("", response_model=APIResponse[list])
async def list_llm_configs(
    api_key: APIKey,
    llm_repo: LLMConfigRepo,
    enabled_only: bool = False,
):
    """
    获取所有 LLM 配置列表
    
    Args:
        enabled_only: 是否只返回启用的配置
    """
    if enabled_only:
        configs = llm_repo.get_enabled()
    else:
        configs = llm_repo.get_all()
    
    result = []
    for cfg in configs:
        result.append(LLMConfigSummary(
            id=cfg.id,
            name=cfg.name,
            display_name=cfg.display_name,
            provider=cfg.provider,
            model_name=cfg.model_name,
            is_enabled=cfg.is_enabled,
            is_default=cfg.is_default,
        ))
    
    return APIResponse(data=result)


@router.get("/default", response_model=APIResponse[LLMConfigDetail])
async def get_default_llm_config(
    api_key: APIKey,
    llm_repo: LLMConfigRepo,
):
    """
    获取默认 LLM 配置
    """
    cfg = llm_repo.get_default()
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default LLM config found"
        )
    
    return APIResponse(data=_to_detail(cfg))


@router.get("/{config_id}", response_model=APIResponse[LLMConfigDetail])
async def get_llm_config(
    config_id: int,
    api_key: APIKey,
    llm_repo: LLMConfigRepo,
):
    """
    获取 LLM 配置详情
    
    API Key 会被脱敏显示
    """
    cfg = llm_repo.get_by_id(config_id)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM Config with id {config_id} not found"
        )
    
    return APIResponse(data=_to_detail(cfg))


# =============================================================================
# Create & Update
# =============================================================================

@router.post("", response_model=APIResponse[LLMConfigDetail], status_code=status.HTTP_201_CREATED)
async def create_llm_config(
    request: LLMConfigCreateRequest,
    api_key: APIKey,
    llm_repo: LLMConfigRepo,
    db: DbSession,
):
    """
    创建新的 LLM 配置
    
    支持的 provider：openai, anthropic, azure, ollama, custom
    """
    # 检查名称是否重复
    existing = llm_repo.get_by_name(request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"LLM Config with name '{request.name}' already exists"
        )
    
    # 创建配置
    cfg = LLMConfig(
        name=request.name,
        display_name=request.display_name,
        description=request.description,
        provider=request.provider,
        model_name=request.model_name,
        base_url=request.base_url,
        api_key=request.api_key,
        temperature=request.temperature,
        max_retries=request.max_retries,
        is_enabled=request.is_enabled,
        is_default=False,  # 创建时不设为默认
    )
    
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    
    return APIResponse(
        data=_to_detail(cfg),
        message=f"LLM Config '{cfg.name}' created successfully"
    )


@router.patch("/{config_id}", response_model=APIResponse[LLMConfigDetail])
async def update_llm_config(
    config_id: int,
    request: LLMConfigUpdateRequest,
    api_key: APIKey,
    llm_repo: LLMConfigRepo,
    db: DbSession,
):
    """
    更新 LLM 配置
    
    只更新提供的字段，未提供的字段保持不变
    """
    cfg = llm_repo.get_by_id(config_id)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM Config with id {config_id} not found"
        )
    
    # 更新字段
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cfg, field, value)
    
    cfg.updated_at = datetime.now()
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    
    return APIResponse(
        data=_to_detail(cfg),
        message=f"LLM Config '{cfg.name}' updated successfully"
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    config_id: int,
    api_key: APIKey,
    llm_repo: LLMConfigRepo,
):
    """
    删除 LLM 配置
    
    警告：删除后无法恢复，关联的 Bot 将无法使用该 LLM
    """
    cfg = llm_repo.get_by_id(config_id)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM Config with id {config_id} not found"
        )
    
    if cfg.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default LLM config"
        )
    
    llm_repo.delete(config_id)


# =============================================================================
# Set Default & Test
# =============================================================================

@router.post("/{config_id}/set-default", response_model=APIResponse[dict])
async def set_default_llm_config(
    config_id: int,
    api_key: APIKey,
    llm_repo: LLMConfigRepo,
):
    """
    设置为默认 LLM 配置
    
    会将其他配置的 is_default 设为 False
    """
    cfg = llm_repo.get_by_id(config_id)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM Config with id {config_id} not found"
        )
    
    if not cfg.is_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set a disabled config as default"
        )
    
    llm_repo.set_as_default(config_id)
    
    return APIResponse(
        data={"config_id": config_id, "is_default": True},
        message=f"LLM Config '{cfg.name}' is now the default"
    )


@router.post("/{config_id}/test", response_model=APIResponse[LLMConfigTestResult])
async def test_llm_config(
    config_id: int,
    api_key: APIKey,
    llm_repo: LLMConfigRepo,
):
    """
    测试 LLM 配置连接
    
    发送一个简单的测试请求验证配置是否有效
    """
    cfg = llm_repo.get_by_id(config_id)
    if not cfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"LLM Config with id {config_id} not found"
        )
    
    try:
        import time
        start = time.time()
        
        # 根据 provider 创建 LLM 实例
        if cfg.provider == "openai":
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(**cfg.to_langchain_kwargs())
        elif cfg.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(**cfg.to_langchain_kwargs())
        else:
            # 通用 OpenAI 兼容
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(**cfg.to_langchain_kwargs())
        
        # 发送测试消息
        response = llm.invoke("Say 'Hello, I am working!' in one short sentence.")
        latency = int((time.time() - start) * 1000)
        
        return APIResponse(
            data=LLMConfigTestResult(
                success=True,
                message="Connection successful",
                response_preview=str(response.content)[:100],
                latency_ms=latency,
            )
        )
        
    except Exception as e:
        return APIResponse(
            data=LLMConfigTestResult(
                success=False,
                message=str(e),
                response_preview=None,
                latency_ms=None,
            )
        )


# =============================================================================
# Helper Functions
# =============================================================================

def _mask_api_key(key: str) -> str:
    """脱敏 API Key"""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def _to_detail(cfg: LLMConfig) -> LLMConfigDetail:
    """转换为详情响应"""
    return LLMConfigDetail(
        id=cfg.id,
        name=cfg.name,
        display_name=cfg.display_name,
        description=cfg.description,
        provider=cfg.provider,
        model_name=cfg.model_name,
        base_url=cfg.base_url,
        api_key_masked=_mask_api_key(cfg.api_key) if cfg.api_key else None,
        temperature=float(cfg.temperature),
        max_retries=cfg.max_retries,
        is_enabled=cfg.is_enabled,
        is_default=cfg.is_default,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )

