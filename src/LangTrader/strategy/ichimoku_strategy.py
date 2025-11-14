import pandas as pd
import pandas_ta as ta
from src.LangTrader.strategy.base_strategy import BaseStrategy

class IchimokuStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("IchimokuStrategy", "This strategy uses the Ichimoku indicator to generate buy and sell signals")

    def calculate_ichimoku(self, df):
        """计算一目均衡表指标"""
        # 转换线 (Tenkan-sen) - 9周期高低点中点
        tenkan_sen = (df['high'].rolling(9).max() + df['low'].rolling(9).min()) / 2
        
        # 基准线 (Kijun-sen) - 26周期高低点中点
        kijun_sen = (df['high'].rolling(26).max() + df['low'].rolling(26).min()) / 2
        
        # 先行带A (Senkou Span A) - 转换线和基准线的中点，向前推26周期
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
        
        # 先行带B (Senkou Span B) - 52周期高低点中点，向前推26周期
        senkou_span_b = ((df['high'].rolling(52).max() + df['low'].rolling(52).min()) / 2).shift(26)
        
        # 迟行带 (Chikou Span) - 当前收盘价向后推26周期
        chikou_span = df['close'].shift(-26)
        
        return tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        close_price = last_row['close']
        simple_prompt = "\n一目均衡表策略信号：\n"
        # 计算一目均衡表指标
        tenkan_sen, kijun_sen, senkou_span_a, senkou_span_b, chikou_span = self.calculate_ichimoku(df)
        
        # 获取最新值
        latest_tenkan = tenkan_sen.iloc[-1]
        latest_kijun = kijun_sen.iloc[-1]
        latest_senkou_a = senkou_span_a.iloc[-1]
        latest_senkou_b = senkou_span_b.iloc[-1]
        latest_chikou = chikou_span.iloc[-27]  # 对应26周期前的价格
        
        # 价格高于云层且转换线上穿基准线 = 强势买入信号
        if (close_price > max(latest_senkou_a, latest_senkou_b) and 
            latest_tenkan > latest_kijun and
            last_row['close'] > latest_chikou):
            simple_prompt += "\n价格高于云层且转换线上穿基准线 = 强势买入信号"
        
        # 价格低于云层且转换线下穿基准线 = 强势卖出信号
        elif (close_price < min(latest_senkou_a, latest_senkou_b) and 
              latest_tenkan < latest_kijun and
              last_row['close'] < latest_chikou):
            simple_prompt += "\n价格低于云层且转换线下穿基准线 = 强势卖出信号"
        
        # 转换线上穿基准线 = 买入信号
        elif latest_tenkan > latest_kijun:
            simple_prompt += "\n转换线上穿基准线 = 买入信号"
        
        # 转换线下穿基准线 = 卖出信号
        elif latest_tenkan < latest_kijun:
            simple_prompt += "\n转换线下穿基准线 = 卖出信号"
        
        else:
            simple_prompt += "\n无明确一目均衡表信号"
        return simple_prompt