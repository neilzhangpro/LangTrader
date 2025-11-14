import pandas as pd
import pandas_ta as ta
from src.LangTrader.strategy.base_strategy import BaseStrategy

class EnhancedMeanReversionStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("EnhancedMeanReversionStrategy", "This strategy uses the enhanced mean reversion to generate buy and sell signals")
        self.z_score_threshold = 2.0

    def calculate_z_score(self, df, period=20):
        """计算Z-Score"""
        prices = df['close']
        mean = prices.rolling(period).mean()
        std = prices.rolling(period).std()
        z_score = (prices - mean) / std
        return z_score

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        close_price = last_row['close']
        simple_prompt = "\n增强均值回归策略信号：\n"
        # 计算Z-Score
        z_score = self.calculate_z_score(df, 20)
        latest_z_score = z_score.iloc[-1]
        
        # 计算RSI确认信号
        rsi = ta.rsi(df['close'], length=14)
        latest_rsi = rsi.iloc[-1] if rsi is not None and len(rsi) > 0 else 50
        
        # 计算布林带确认信号
        bbands = ta.bbands(df['close'], length=20, std=2)
        bb_lower = bbands.iloc[-1, 0] if bbands is not None and len(bbands) > 0 else close_price
        bb_upper = bbands.iloc[-1, 2] if bbands is not None and len(bbands) > 0 else close_price
        
        # 超卖且Z-Score低 = 强烈买入信号
        if latest_z_score < -self.z_score_threshold and latest_rsi < 30:
            confidence = min(0.9, abs(latest_z_score) / self.z_score_threshold)
            simple_prompt += f"\n严重超卖 (Z-Score: {latest_z_score:.2f}, RSI: {latest_rsi:.1f})"
        
        # 超买且Z-Score高 = 强烈卖出信号
        elif latest_z_score > self.z_score_threshold and latest_rsi > 70:
            confidence = min(0.9, abs(latest_z_score) / self.z_score_threshold)
            simple_prompt += f"\n严重超买 (Z-Score: {latest_z_score:.2f}, RSI: {latest_rsi:.1f})"
        
        # 轻微超卖 = 买入信号
        elif latest_z_score < -1 and latest_rsi < 40:
            confidence = min(0.7, abs(latest_z_score))
            simple_prompt += f"\n轻微超卖 (Z-Score: {latest_z_score:.2f}, RSI: {latest_rsi:.1f})"
        
        # 轻微超买 = 卖出信号
        elif latest_z_score > 1 and latest_rsi > 60:
            confidence = min(0.7, abs(latest_z_score))
            simple_prompt += f"\n轻微超买 (Z-Score: {latest_z_score:.2f}, RSI: {latest_rsi:.1f})"
        
        else:
            simple_prompt += f"\n价格处于均值附近 (Z-Score: {latest_z_score:.2f}, RSI: {latest_rsi:.1f})"
        return simple_prompt