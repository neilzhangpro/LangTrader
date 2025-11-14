from src.LangTrader.strategy.base_strategy import BaseStrategy
import pandas as pd

class EMA20Strategy(BaseStrategy):
    def __init__(self):
        super().__init__("EMA20Strategy", "This strategy uses the EMA20 indicator to generate buy and sell signals")

    def generate_signal(self,symbol:str, df:pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        simple_prompt = "\nEMA20策略信号：\n"
        if last_row['SMA_20'] > last_row['close']:
            simple_prompt += "\nSMA greater than current price, sell signal"
        elif last_row['EMA_20'] < last_row['close']:
            simple_prompt += "\nEMA less than current price, buy signal"
        else:
            simple_prompt += "\nSMA and EMA between, hold signal"
        return simple_prompt