from src.LangTrader.strategy.base_strategy import BaseStrategy
import pandas as pd

class BBUStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("BBUStrategy", "This strategy uses the BBU indicator to generate buy and sell signals")

    def generate_signal(self,symbol:str, df:pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        simple_prompt = f"\n布林带策略信号：\n"
        if last_row['BBU_20_2.0_2.0'] > last_row['close']:
            if last_row['BBU_20_2.0_2.0'] > last_row['BBP_20_2.0_2.0']:
                simple_prompt += "\nUpper band greater than current price, sell signal"
            else:
                simple_prompt += "\nUpper band and lower band between, hold signal"
        elif last_row['BBP_20_2.0_2.0'] < last_row['close']:
            if last_row['BBP_20_2.0_2.0'] < last_row['BBU_20_2.0_2.0']:
                simple_prompt += "\nLower band less than current price, buy signal"
            else:
                simple_prompt += "\nUpper band and lower band between, hold signal"
        else:
            simple_prompt += "\nUpper band and lower band between, hold signal"
        return simple_prompt