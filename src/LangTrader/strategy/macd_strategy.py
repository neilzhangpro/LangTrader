from src.LangTrader.strategy.base_strategy import BaseStrategy
import pandas as pd

class MACDStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("MACD Strategy", "This strategy uses the MACD indicator to generate buy and sell signals")

    def generate_signal(self,symbol:str, df:pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        simple_prompt = "\nMACD策略信号：\n"
        if last_row['MACD_12_26_9'] > last_row['MACDs_12_26_9']:
            simple_prompt += f"\nMACD greater than MACD Signal, SELL + SHORT"
        elif last_row['MACD_12_26_9'] < last_row['MACDs_12_26_9']:
            simple_prompt += f"\nMACD less than MACD Signal, BUY + LONG"
        else:
            simple_prompt += f"\nMACD equal to MACD Signal, HOLD signal"
        return simple_prompt