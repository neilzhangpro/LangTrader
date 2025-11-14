from src.LangTrader.strategy.base_strategy import BaseStrategy
import pandas as pd
class RSIStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("RSI Strategy", "This strategy uses the RSI indicator to generate buy and sell signals")

    def generate_signal(self,symbol:str, df:pd.DataFrame) -> dict:
        last_row = df.iloc[-1]
        simple_prompt = "\nRSI策略信号：\n"
        if last_row['RSI_14'] > 70:
            simple_prompt += f"\nRSI greater than 70, SELL + SHORT"
        elif last_row['RSI_14'] < 30:
            simple_prompt += f"\nRSI less than 30, BUY + LONG"
        else:
            simple_prompt += f"\nRSI between 30 and 70, HOLD signal"
        return simple_prompt