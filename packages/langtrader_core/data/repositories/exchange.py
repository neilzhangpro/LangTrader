# packages/langtrader_core/data/repositories/exchange.py
from sqlmodel import select, Session
from ..models.exchange import exchange
from typing import List, Optional
from sqlalchemy import delete


class ExchangeRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, exchange_obj: exchange) -> exchange:
        """
        save the exchange
        """
        self.session.add(exchange_obj)
        self.session.commit()
        self.session.refresh(exchange_obj)
        return exchange_obj
    
    def get_by_id(self, exchange_id: int) -> Optional[exchange]:
        """
        get the exchange by id
        """
        statement = select(exchange).where(exchange.id == exchange_id)
        result = self.session.exec(statement).first()
        return result.model_dump() if result else None
    
    def get_all(self) -> List[exchange]:
        """
        get all the exchanges
        """
        statement = select(exchange)
        results = self.session.exec(statement).all()
        return [result.model_dump() for result in results] if results else []
    
    def delete(self, exchange_id: int):
        """
        delete the exchange by id
        """
        statement = delete(exchange).where(exchange.id == exchange_id)
        self.session.exec(statement)
        self.session.commit()
    
    def update(self, exchange_obj: exchange) -> exchange:
        """
        update the exchange
        """
        self.session.add(exchange_obj)
        self.session.commit()
        self.session.refresh(exchange_obj)
        return exchange_obj