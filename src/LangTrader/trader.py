from src.LangTrader.config import Config
from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from src.LangTrader.market import CryptoFetcher
from src.LangTrader.db import Database

class Trader:
    def __init__(self,config:Config):
        self.config = config
        self.hyperliquid = hyperliquidAPI()
        self.fetcher = CryptoFetcher()
        self.db = Database()
        self.symbols = config.symbols

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