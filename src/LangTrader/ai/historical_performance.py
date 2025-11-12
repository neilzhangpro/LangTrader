from src.LangTrader.utils import logger
from src.LangTrader.config import Config
from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from src.LangTrader.market import CryptoFetcher
from src.LangTrader.db import Database
import json

class HistoricalPerformance:
    def __init__(self,config:Config):
        self.config = config
        self.hyperliquid = hyperliquidAPI()
        self.fetcher = CryptoFetcher()
        self.db = Database()
        self.symbols = config.symbols
    
    def get_20_decision_info(self,trader_id:str):
        logger.info("-----Start Get 20 Decision Info------")
        recent_decisions = self.db.execute("""
        SELECT * FROM decisions
        WHERE trader_id = %s
        ORDER BY created_at DESC
        LIMIT 3
        """,(trader_id,))
        if not recent_decisions:
            logger.warning("No recent decisions found")
            return None
        prompt_info = ""
        for decision in recent_decisions:
            prompt_info += f"Symbol: {decision['symbol']}\nAction: {decision['action']}\\nConfidence: {decision['confidence']}"
            llmanalysis = decision['llm_analysis']
            prompt_info +=f"决策结果: {llmanalysis}\n决策时间: {decision['created_at']}\n"
        return prompt_info

    def get_20_position_info(self,trader_id:str):
        recent_positions = self.db.execute("""
        SELECT * FROM positions
        WHERE trader_id = %s
        AND status = 'closed'
        ORDER BY opened_at DESC
        LIMIT 20
        """,(trader_id,))
        if not recent_positions:
            return None
        position_info = {}
        for position in recent_positions:
            position_info[position["symbol"]] = {
                "entry_price": position["entry_price"],
                "quantity": position["quantity"],
            }
        return recent_positions