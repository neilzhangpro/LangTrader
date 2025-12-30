# packages/langtrader_core/data/repositories/bot.py
from sqlmodel import select, Session
from langtrader_core.data.models.bot import Bot
from typing import List, Optional
from langtrader_core.utils import get_logger
logger = get_logger("bot_repository")
from datetime import datetime

class BotRepository:
    """Bot 仓储"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, **kwargs) -> Bot:
        """创建机器人"""
        bot = Bot(**kwargs)
        self.session.add(bot)
        self.session.commit()
        self.session.refresh(bot)
        logger.info(f"✅ Created bot: {bot.name}")
        return bot
    
    def get_by_id(self, bot_id: int) -> Optional[Bot]:
        """通过ID获取机器人"""
        statement = select(Bot).where(Bot.id == bot_id)
        bot = self.session.exec(statement).first()
        if bot:
            logger.info(f"✅ Got bot: {bot.name}")
        return bot
    
    def get_by_name(self, name: str) -> Optional[Bot]:
        """通过名称获取机器人"""
        statement = select(Bot).where(Bot.name == name)
        bot = self.session.exec(statement).first()
        if bot:
            logger.info(f"✅ Got bot: {bot.name}")
        return bot
    
    def get_active_bots(self) -> List[Bot]:
        """获取所有活跃的机器人"""
        statement = select(Bot).where(Bot.is_active == True)
        bots = list(self.session.exec(statement).all())
        if bots:
            logger.info(f"✅ Got active bots: {len(bots)}")
        return bots
    
    def get_bots_by_exchange(self, exchange_id: int) -> List[Bot]:
        """获取指定交易所的所有机器人"""
        statement = select(Bot).where(Bot.exchange_id == exchange_id)
        bots = list(self.session.exec(statement).all())
        if bots:
            logger.info(f"✅ Got bots by exchange: {exchange_id} ({len(bots)})")
        return bots
    
    def update(self, bot: Bot) -> Bot:
        """更新机器人"""
        bot.updated_at = datetime.now()
        self.session.add(bot)
        self.session.commit()
        self.session.refresh(bot)
        logger.info(f"✅ Updated bot: {bot.name}")
        return bot
    
    def deactivate(self, bot_id: int):
        """停用机器人"""
        bot = self.get_by_id(bot_id)
        if bot:
            bot.is_active = False
            bot.updated_at = datetime.now()
            self.session.commit()
            logger.info(f"✅ Deactivated bot: {bot.name}")
        else:
            logger.warning(f"🔍 Bot {bot_id} not found")