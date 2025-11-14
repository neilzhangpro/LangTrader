from src.LangTrader.strategy.base_strategy import BaseStrategy
import pandas as pd

class VolumeStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("VolumeStrategy", "This strategy uses the volume to generate buy and sell signals")

    def generate_signal(self,symbol:str, df:pd.DataFrame) -> str:
        last_row = df.iloc[-1]
        simple_prompt = "\n成交量策略信号：\n "
        if last_row['volume_rsi'] > 70:
            simple_prompt += "\nVolume RSI greater than 70, SELL + SHORT"
        elif last_row['volume_rsi'] < 30:
            simple_prompt += "\nVolume RSI less than 30, BUY + LONG"
        else:
            simple_prompt += "\nVolume RSI between 30 and 70, hold signal"
        if last_row['volume_ratio'] > 1:
            simple_prompt += "\nVolume ratio greater than 1, sell signal"
        elif last_row['volume_ratio'] < 1:
            simple_prompt += "\nVolume ratio less than 1, buy signal"
        else:
            simple_prompt += "\nVolume ratio equal to 1, hold signal"
        if last_row['volume_sma_20'] > last_row['volume']:
            simple_prompt += "\nVolume SMA 20 greater than volume, sell signal"
        elif last_row['volume_sma_20'] < last_row['volume']:
            simple_prompt += "\nVolume SMA 20 less than volume, buy signal"
        else:
            simple_prompt += "\nVolume SMA 20 equal to volume, hold signal"
        if last_row['volume'] > last_row['volume_sma_20']:
            simple_prompt += "\nVolume greater than volume SMA 20, sell signal"
        elif last_row['volume'] < last_row['volume_sma_20']:
            simple_prompt += "\nVolume less than volume SMA 20, buy signal"
        else:
            simple_prompt += "\nVolume equal to volume SMA 20, hold signal"
        if last_row['volume'] > last_row['volume_sma_20']:
            simple_prompt += "\nVolume greater than volume SMA 20, sell signal"
        elif last_row['volume'] < last_row['volume_sma_20']:
            simple_prompt += "\nVolume less than volume SMA 20, buy signal"
        else:
            simple_prompt += "\nVolume equal to volume SMA 20, hold signal"
        if last_row['volume'] > last_row['volume_rsi']:
            simple_prompt += "\nVolume greater than volume RSI, sell signal"
        elif last_row['volume'] < last_row['volume_rsi']:
            simple_prompt += "\nVolume less than volume RSI, buy signal"
        else:
            simple_prompt += "\nVolume equal to volume RSI, hold signal"
        if last_row['volume'] > last_row['volume_ratio']:
            simple_prompt += "\nVolume greater than volume ratio, sell signal"
        elif last_row['volume'] < last_row['volume_ratio']:
            simple_prompt += "\nVolume less than volume ratio, buy signal"
        else:
            simple_prompt += "\nVolume equal to volume ratio, hold signal"
        return simple_prompt