import pandas as pd
import numpy as np
from src.LangTrader.strategy.base_strategy import BaseStrategy

class SupportResistanceStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("SupportResistanceStrategy", "This strategy uses the support and resistance levels to generate buy and sell signals")

    def find_pivots(self, df):
        """寻找支撑位和阻力位"""
        highs = df['high']
        lows = df['low']
        closes = df['close']
        
        # 计算枢轴点
        pivot = (highs + lows + closes) / 3
        resistance1 = (2 * pivot) - lows
        support1 = (2 * pivot) - highs
        
        return pivot, support1, resistance1

    def generate_signal(self,symbol:str, df:pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        close_price = last_row['close']
        simple_prompt = "\n支撑阻力策略信号：\n"
        # 计算枢轴点
        pivot, support1, resistance1 = self.find_pivots(df)
        
        # 获取最新的枢轴点值
        current_pivot = pivot.iloc[-1]
        current_support = support1.iloc[-1]
        current_resistance = resistance1.iloc[-1]

        #信号判断
        if close_price > current_resistance:
            simple_prompt +=f"\n价格突破阻力位{current_resistance}, SELL + SHORT"
        elif close_price < current_support:
            simple_prompt +=f"\n价格突破支撑位{current_support}, BUY + LONG"
        elif close_price > current_pivot:
            simple_prompt +=f"\n价格突破枢轴点{current_pivot}, SELL + SHORT"
        else:
            simple_prompt +=f"\n价格在枢轴点附近震荡, HOLD signal"
        return simple_prompt