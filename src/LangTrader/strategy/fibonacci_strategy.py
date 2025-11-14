import pandas as pd
import numpy as np
from src.LangTrader.strategy.base_strategy import BaseStrategy

class FibonacciStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("FibonacciStrategy", "This strategy uses the Fibonacci retracement to generate buy and sell signals")
        self.fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]

    def calculate_fibonacci_levels(self, df, period=30):
        """计算斐波那契回调位"""
        # 获取周期内的最高价和最低价
        recent_high = df['high'].tail(period).max()
        recent_low = df['low'].tail(period).min()
        
        # 计算价格差
        price_range = recent_high - recent_low
        
        # 计算回调位
        fib_levels = {}
        for level in self.fib_levels:
            fib_levels[level] = recent_high - (price_range * level)
            
        return fib_levels, recent_high, recent_low

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        close_price = last_row['close']
        simple_prompt = "\n斐波那契策略信号：\n"

        # 计算斐波那契回调位
        fib_levels, recent_high, recent_low = self.calculate_fibonacci_levels(df)
        
        # 检查价格是否接近关键回调位
        for level, price in fib_levels.items():
            # 如果价格接近回调位（±1%范围内）
            if abs(close_price - price) / price < 0.01:
                if level in [0.382, 0.5, 0.618]:  #
                    if close_price > price:
                        simple_prompt += f"\n价格在{level*100:.1f}%斐波那契回调位{price:.2f}附近反弹"
                    else:
                        simple_prompt += f"\n价格在{level*100:.1f}%斐波那契回调位{price:.2f}附近回落"
                else:
                    simple_prompt += f"\n价格在斐波那契回调位{price:.2f}附近, HOLD"
            
        return simple_prompt