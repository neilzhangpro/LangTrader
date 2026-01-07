# packages/langtrader_core/data/repositories/system_config.py
"""
系统配置仓储
"""
from sqlmodel import Session, select
from sqlalchemy import distinct
from typing import List, Optional
from datetime import datetime

from langtrader_core.data.models.system_config import SystemConfigModel


class SystemConfigRepository:
    """系统配置仓储"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_all(self, category: Optional[str] = None) -> List[SystemConfigModel]:
        """获取所有配置"""
        stmt = select(SystemConfigModel)
        if category:
            stmt = stmt.where(SystemConfigModel.category == category)
        stmt = stmt.order_by(SystemConfigModel.config_key)
        return list(self.session.exec(stmt).all())
    
    def get_by_key(self, config_key: str) -> Optional[SystemConfigModel]:
        """通过 key 获取配置"""
        stmt = select(SystemConfigModel).where(SystemConfigModel.config_key == config_key)
        return self.session.exec(stmt).first()
    
    def get_by_id(self, config_id: int) -> Optional[SystemConfigModel]:
        """通过 ID 获取配置"""
        return self.session.get(SystemConfigModel, config_id)
    
    def get_by_prefix(self, prefix: str) -> List[SystemConfigModel]:
        """通过前缀获取配置"""
        stmt = select(SystemConfigModel).where(
            SystemConfigModel.config_key.startswith(prefix)
        ).order_by(SystemConfigModel.config_key)
        return list(self.session.exec(stmt).all())
    
    def create(self, config: SystemConfigModel) -> SystemConfigModel:
        """创建配置"""
        config.updated_at = datetime.now()
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return config
    
    def update(self, config_id: int, updates: dict) -> Optional[SystemConfigModel]:
        """更新配置"""
        config = self.get_by_id(config_id)
        if not config:
            return None
        
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_at = datetime.now()
        self.session.add(config)
        self.session.commit()
        self.session.refresh(config)
        return config
    
    def upsert(self, config_key: str, config_value: str, **kwargs) -> SystemConfigModel:
        """
        创建或更新配置（通过 key）
        
        Args:
            config_key: 配置键
            config_value: 配置值
            **kwargs: 其他字段（value_type, category, description, is_editable）
        """
        existing = self.get_by_key(config_key)
        
        if existing:
            # 更新
            existing.config_value = config_value
            for key, value in kwargs.items():
                if hasattr(existing, key) and value is not None:
                    setattr(existing, key, value)
            existing.updated_at = datetime.now()
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing
        else:
            # 创建
            config = SystemConfigModel(
                config_key=config_key,
                config_value=config_value,
                **kwargs
            )
            return self.create(config)
    
    def delete(self, config_id: int) -> bool:
        """删除配置"""
        config = self.get_by_id(config_id)
        if not config:
            return False
        self.session.delete(config)
        self.session.commit()
        return True
    
    def delete_by_key(self, config_key: str) -> bool:
        """通过 key 删除配置"""
        config = self.get_by_key(config_key)
        if not config:
            return False
        self.session.delete(config)
        self.session.commit()
        return True
    
    def get_categories(self) -> List[str]:
        """获取所有类别"""
        stmt = select(distinct(SystemConfigModel.category)).where(
            SystemConfigModel.category.isnot(None)
        )
        result = self.session.exec(stmt).all()
        return [row for row in result if row]

