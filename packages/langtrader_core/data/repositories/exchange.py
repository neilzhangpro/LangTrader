# packages/langtrader_core/data/repositories/exchange.py
"""
交易所配置仓库
"""
from sqlmodel import select, Session
from ..models.exchange import exchange
from typing import List, Optional, Dict, Any
from sqlalchemy import delete


class ExchangeRepository:
    """交易所配置仓库"""
    
    def __init__(self, session: Session):
        self.session = session

    def save(self, exchange_obj: exchange) -> exchange:
        """保存交易所配置"""
        self.session.add(exchange_obj)
        self.session.commit()
        self.session.refresh(exchange_obj)
        return exchange_obj
    
    def get_by_id(self, exchange_id: int) -> Optional[Dict[str, Any]]:
        """获取交易所配置"""
        statement = select(exchange).where(exchange.id == exchange_id)
        result = self.session.exec(statement).first()
        if result:
            return {
                "id": result.id,
                "type": result.type,
                "name": result.name,
                "apikey": result.apikey,
                "secretkey": result.secretkey,
                "uid": result.uid,
                "password": result.password,
                "testnet": result.testnet,
                "IoTop": result.IoTop,
                "slippage": result.slippage,
            }
        return None
    
    def get_by_id_model(self, exchange_id: int) -> Optional[exchange]:
        """获取交易所模型对象（用于更新操作）"""
        statement = select(exchange).where(exchange.id == exchange_id)
        return self.session.exec(statement).first()
    
    def get_all(self) -> List[Dict[str, Any]]:
        """获取所有交易所配置"""
        statement = select(exchange)
        results = self.session.exec(statement).all()
        if results:
            return [
                {
                    "id": r.id,
                    "type": r.type,
                    "name": r.name,
                    "apikey": r.apikey,
                    "secretkey": r.secretkey,
                    "uid": r.uid,
                    "password": r.password,
                    "testnet": r.testnet,
                    "IoTop": r.IoTop,
                    "slippage": r.slippage,
                }
                for r in results
            ]
        return []
    
    def delete(self, exchange_id: int):
        """删除交易所配置"""
        statement = delete(exchange).where(exchange.id == exchange_id)
        self.session.exec(statement)
        self.session.commit()
    
    def update(self, exchange_obj: exchange) -> exchange:
        """更新交易所配置"""
        self.session.add(exchange_obj)
        self.session.commit()
        self.session.refresh(exchange_obj)
        return exchange_obj
