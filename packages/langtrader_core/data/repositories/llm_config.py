# packages/langtrader_core/data/repositories/llm_config.py

from sqlmodel import select, Session
from ..models.llm_config import LLMConfig
from typing import List, Optional
from sqlalchemy import delete


class LLMConfigRepository:
    """LLM 配置仓储"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def save(self, config: LLMConfig) -> LLMConfig:
        """保存 LLM 配置"""
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return config
    
    def get_by_id(self, config_id: int) -> Optional[LLMConfig]:
        """根据 ID 获取配置"""
        statement = select(LLMConfig).where(LLMConfig.id == config_id)
        return self.session.exec(statement).first()
    
    def get_by_name(self, name: str) -> Optional[LLMConfig]:
        """根据名称获取配置"""
        statement = select(LLMConfig).where(LLMConfig.name == name)
        return self.session.exec(statement).first()
    
    def get_default(self) -> Optional[LLMConfig]:
        """获取默认 LLM 配置"""
        statement = select(LLMConfig).where(
            LLMConfig.is_default == True,
            LLMConfig.is_enabled == True
        )
        return self.session.exec(statement).first()
    
    def get_all(self) -> List[LLMConfig]:
        """获取所有配置"""
        statement = select(LLMConfig)
        results = self.session.exec(statement).all()
        return list(results)
    
    def get_enabled(self) -> List[LLMConfig]:
        """获取所有启用的配置"""
        statement = select(LLMConfig).where(LLMConfig.is_enabled == True)
        results = self.session.exec(statement).all()
        return list(results)
    
    def get_by_provider(self, provider: str) -> List[LLMConfig]:
        """根据提供者获取配置"""
        statement = select(LLMConfig).where(LLMConfig.provider == provider)
        results = self.session.exec(statement).all()
        return list(results)
    
    def update(self, config: LLMConfig) -> LLMConfig:
        """更新配置"""
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return config
    
    def delete(self, config_id: int):
        """删除配置"""
        statement = delete(LLMConfig).where(LLMConfig.id == config_id)
        self.session.exec(statement)
        self.session.commit()
    
    def set_as_default(self, config_id: int):
        """设置为默认配置"""
        # 先将所有配置的 is_default 设为 False
        all_configs = self.get_all()
        for cfg in all_configs:
            cfg.is_default = False
            self.session.add(cfg)
        
        # 再将指定配置设为 True
        config = self.get_by_id(config_id)
        if config:
            config.is_default = True
            self.session.add(config)
        
        self.session.commit()