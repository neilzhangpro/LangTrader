from src.LangTrader.market import CryptoFetcher
import pandas as pd
from src.LangTrader.utils import logger

class MarketAnalysis:
    def __init__(self, symbols:str):
        self.symbols = symbols
        self.fetcher = CryptoFetcher()

    def get_market_data(self, state):
        market_data = ""
        key_indicators = {}  # 存储关键指标（可序列化）
        for symbol in self.symbols:
            logger.info(f"Symbol--->: {symbol}")
            fetcher = self.fetcher
            self.fetcher.symbol = symbol
            
            try:
                current_price = fetcher.get_current_price()
                df = fetcher.get_OHLCV()
                df = fetcher.get_technical_indicators(df)
                
                # 只提取最后一行的关键指标
                last_row = df.iloc[-1]
                
                # 提取并转换为可序列化的格式
                symbol_indicators = {}
                for col in df.columns:
                    value = last_row[col]
                    # 处理不同类型的值
                    if pd.isna(value):
                        symbol_indicators[col] = None
                    elif isinstance(value, pd.Timestamp):
                        symbol_indicators[col] = str(value)
                    elif isinstance(value, (int, float)):
                        symbol_indicators[col] = float(value)
                    else:
                        symbol_indicators[col] = str(value)
                
                key_indicators[symbol] = symbol_indicators
                
                # 生成文本描述
                simple_prompt = fetcher.get_simple_trade_signal(df)
                logger.info(f"Simple prompt: {simple_prompt}")

                symbol_positions = state.get("current_positions", {}) or {}
                position_key = symbol.upper()
                symbol_position = symbol_positions.get(position_key) or symbol_positions.get(symbol)

                if symbol_position:
                    position_description = (
                        f"当前持仓:\n"
                        f"- 方向: {'做多' if symbol_position.get('side') == 'long' else '做空'}\n"
                        f"- 仓位大小: {abs(symbol_position.get('size', 0)):.4f}\n"
                        f"- 入场价格: ${symbol_position.get('entry_price', 0):.4f}\n"
                        f"- 当前价格: ${symbol_position.get('current_price', 0):.4f}\n"
                        f"- 未实现盈亏: ${symbol_position.get('unrealized_pnl', 0):.2f} ({symbol_position.get('pnl_percentage', 0):+.2f}%)\n"
                        f"- 杠杆: {symbol_position.get('leverage', 0):.2f}x\n"
                        f"- 强平价格: ${symbol_position.get('liquidation_price', 0):.4f}\n"
                        f"- 距离强平: {symbol_position.get('distance_to_liquidation_pct', 0):.2f}%"
                    )
                else:
                    position_description = "当前无此合约持仓"

                market_data += (
                    f"---------------{symbol}-------------------\n"
                    f"{simple_prompt}\n"
                    f"-----------------------------------\n"
                    f"{position_description}\n\n"
                )
                
            except Exception as e:
                logger.error(f"获取 {symbol} 市场数据失败: {e}")
                key_indicators[symbol] = {}
                market_data += f"---------------{symbol}-------------------\n数据获取失败: {e}\n\n"
        return market_data, key_indicators