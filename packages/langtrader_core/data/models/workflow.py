# packages/langtrader_core/data/models/workflow.py
from sqlmodel import SQLModel, Field, Relationship, Column
from sqlalchemy import ARRAY, String
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


class Workflow(SQLModel, table=True):
    """
    Workflow 策略定义（可复用）
    只包含策略本身的定义，不包含运行时配置
    """
    __tablename__ = "workflows"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 基本信息
    name: str = Field(unique=True, index=True)
    display_name: Optional[str] = None
    version: str = Field(default="1.0.0")
    description: Optional[str] = None
    
    # 分类
    category: str = Field(default="trading")
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(ARRAY(String)))
    
    # 状态
    is_active: bool = Field(default=True)
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[str] = None
    
    # 关系
    nodes: List["WorkflowNode"] = Relationship(back_populates="workflow")
    edges: List["WorkflowEdge"] = Relationship(back_populates="workflow")


class WorkflowNode(SQLModel, table=True):
    """Workflow 节点表"""
    __tablename__ = "workflow_nodes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflows.id")
    
    name: str  # 节点实例名
    plugin_name: str  # 插件名
    display_name: Optional[str] = None  # 显示名称
    description: Optional[str] = None  # 节点描述
    
    enabled: bool = Field(default=True)
    execution_order: int = Field(default=0)
    condition: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 关系
    workflow: Workflow = Relationship(back_populates="nodes")
    configs: List["NodeConfig"] = Relationship(back_populates="node")


class NodeConfig(SQLModel, table=True):
    """节点配置表"""
    __tablename__ = "node_configs"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: int = Field(foreign_key="workflow_nodes.id")
    
    config_key: str
    config_value: str  # JSON string
    value_type: str = Field(default="string")  # string, integer, boolean, json
    
    description: Optional[str] = None
    is_secret: bool = Field(default=False)
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 关系
    node: WorkflowNode = Relationship(back_populates="configs")
    
    def get_value(self) -> Any:
        """解析配置值"""
        if self.value_type == "integer":
            return int(self.config_value)
        elif self.value_type == "boolean":
            return self.config_value.lower() in ("true", "1", "yes")
        elif self.value_type == "json":
            return json.loads(self.config_value)
        else:
            return self.config_value
    
    def set_value(self, value: Any):
        """设置配置值"""
        if isinstance(value, bool):
            self.value_type = "boolean"
            self.config_value = str(value)
        elif isinstance(value, int):
            self.value_type = "integer"
            self.config_value = str(value)
        elif isinstance(value, (dict, list)):
            self.value_type = "json"
            self.config_value = json.dumps(value)
        else:
            self.value_type = "string"
            self.config_value = str(value)


class WorkflowEdge(SQLModel, table=True):
    """Workflow 边表"""
    __tablename__ = "workflow_edges"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    workflow_id: int = Field(foreign_key="workflows.id")
    
    from_node: str
    to_node: str
    condition: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.now)
    
    # 关系
    workflow: Workflow = Relationship(back_populates="edges")