import pandas as pd
import pandas_ta as ta
from src.LangTrader.strategy.base_strategy import BaseStrategy

class VolatilityBreakoutStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("VolatilityBreakoutStrategy", "This strategy uses the volatility breakout to generate buy and sell signals")
        self.period = 14
        self.multiplier = 2
        self.atr_period = 14

    def generate_signal(self,symbol:str, df:pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        simple_prompt = "\n波动突破策略信号：\n"
        close_price = last_row['close']
        high_price = last_row['high']
        low_price = last_row['low']
        
        # 计算ATR
        atr = ta.atr(df['high'], df['low'], df['close'], length=self.period)
        if atr is None or len(atr) == 0:
            simple_prompt += "\nATR is None or length is 0"
        
        latest_atr = atr.iloc[-1]
        
        # 计算上下轨
        upper_band = close_price + (latest_atr * self.multiplier)
        lower_band = close_price - (latest_atr * self.multiplier)
        
        # 获取前一周期的高低点
        prev_high = df['high'].iloc[-2]
        prev_low = df['low'].iloc[-2]
        
        # 向上突破信号
        if high_price > upper_band and prev_high <= upper_band:
            simple_prompt += f"\n价格向上突破波动率轨道 {upper_band:.2f}"
        
        # 向下突破信号
        elif low_price < lower_band and prev_low >= lower_band:
            simple_prompt += f"\n价格向下突破波动率轨道 {lower_band:.2f}"
        
        else:
            simple_prompt += "\n价格未突破波动率轨道"
        return simple_prompt