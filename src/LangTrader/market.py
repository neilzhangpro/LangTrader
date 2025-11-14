import requests
import pandas as pd
import pandas_ta as ta
from src.LangTrader.utils import logger
from src.LangTrader.strategy.rsi_strategy import RSIStrategy
from src.LangTrader.strategy.macd_strategy import MACDStrategy
from src.LangTrader.strategy.bbu_strategy import BBUStrategy
from src.LangTrader.strategy.ema_strategy import EMA20Strategy
from src.LangTrader.strategy.volume_strategy import VolumeStrategy
from src.LangTrader.strategy.support_resistance_strategy import SupportResistanceStrategy
from src.LangTrader.strategy.fibonacci_strategy import FibonacciStrategy
from src.LangTrader.strategy.ichimoku_strategy import IchimokuStrategy
from src.LangTrader.strategy.volatility_breakout_strategy import VolatilityBreakoutStrategy
from src.LangTrader.strategy.enhanced_mean_reversion_strategy import EnhancedMeanReversionStrategy

class CryptoFetcher:
    """This class is used to fetch data from exchange API"""
    def __init__(self, symbol:str = "ETH"):
        self.symbol = symbol
        self.exchange_base = "https://api.exchange.coinbase.com"
        self.data_base = "https://api.coinbase.com/v2"
        self.strategies = [RSIStrategy(), MACDStrategy(), BBUStrategy(), EMA20Strategy(), VolumeStrategy(), SupportResistanceStrategy(), FibonacciStrategy(), IchimokuStrategy(), VolatilityBreakoutStrategy(), EnhancedMeanReversionStrategy()]

    def get_current_price(self):
        url = f"{self.data_base}/prices/{self.symbol}-USD/spot"
        response = requests.get(url)
        data = response.json()
        logger.info(f"Current price of {self.symbol}: {data['data']['amount']}")
        return data['data']['amount']

    def get_OHLCV(self,granularity=3600,limit=300):
        url = f"{self.exchange_base}/products/{self.symbol}-USD/candles"
        params = {"granularity":granularity,"limit":limit}
        response = requests.get(url,params=params)
        data = response.json()
        #Convert to pandas dataframe
        df = pd.DataFrame(data, columns=['time', 'low', 'high', 'open', 'close', 'volume'])
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.sort_values('time').reset_index(drop=True)
        return df

    def get_technical_indicators(self,df):
        #rsi
        rsi = ta.rsi(df["close"],length=14)
        df = pd.concat([df,rsi],axis=1)
        #macd
        macd = ta.macd(df["close"],fast=12,slow=26,signal=9)
        df = pd.concat([df,macd],axis=1)
        #bbands
        bbands = ta.bbands(df["close"],length=20,std=2)
        df = pd.concat([df,bbands],axis=1)
        #sma ema
        sma_20 = ta.sma(df["close"],length=20)
        ema_20 = ta.ema(df["close"],length=20)
        df = pd.concat([df,sma_20,ema_20],axis=1)
        #volume
        # 添加交易量相关指标
        # 成交量移动平均线
        volume_sma = ta.sma(df["volume"], length=20)
        if volume_sma is not None:
            df['volume_sma_20'] = volume_sma
            # 成交量比率
            df['volume_ratio'] = df["volume"] / df['volume_sma_20']
        
        # 成交量RSI
        volume_rsi = ta.rsi(df["volume"], length=14)
        if volume_rsi is not None:
            df['volume_rsi'] = volume_rsi
        return df

    def get_simple_trade_signal(self,df):
        last_row = df.iloc[-1]
        prompts = ""
        logger.info("--------------Simple Prompt------------------")
        logger.info("This is the simplest trading data from coinbase, and the simple trading signal is generated based on the technical indicators.")
        logger.info(f"Current coin: {self.symbol}")
        logger.info(f"Current price: {last_row['close']:,.2f} USD")
        logger.info(f"24 hours highest price: {last_row['high']:,.2f} USD")
        logger.info(f"24 hours lowest price: {last_row['low']:,.2f} USD")
        logger.info(f"24 hours volume: {last_row['volume']:,.2f} {self.symbol}")
        logger.info(f"RSI: {last_row['RSI_14']:,.2f}")
        logger.info(f"MACD: {last_row['MACD_12_26_9']:,.2f}")
        logger.info(f"MACD Signal: {last_row['MACDs_12_26_9']:,.2f}")
        logger.info(f"MACD Hist: {last_row['MACDh_12_26_9']:,.2f}")
        logger.info(f"Upper Band: {last_row['BBU_20_2.0_2.0']:,.2f}")
        logger.info(f"Middle Band: {last_row['BBB_20_2.0_2.0']:,.2f}")
        logger.info(f"Lower Band: {last_row['BBP_20_2.0_2.0']:,.2f}")
        logger.info(f"SMA 20: {last_row['SMA_20']:,.2f}")
        logger.info(f"EMA 20: {last_row['EMA_20']:,.2f}")
        logger.info(f"Volume: {last_row['volume']:,.2f}")
        prompts += f"Current coin: {self.symbol}\nCurrent price: {last_row['close']:,.2f} USD\n24 hours highest price: {last_row['high']:,.2f} USD\n24 hours lowest price: {last_row['low']:,.2f} USD\n24 hours volume: {last_row['volume']:,.2f} ETH\nRSI: {last_row['RSI_14']:,.2f}\nMACD: {last_row['MACD_12_26_9']:,.2f}\nMACD Signal: {last_row['MACDs_12_26_9']:,.2f}\nMACD Hist: {last_row['MACDh_12_26_9']:,.2f}\nUpper Band: {last_row['BBU_20_2.0_2.0']:,.2f}\nMiddle Band: {last_row['BBB_20_2.0_2.0']:,.2f}\nLower Band: {last_row['BBP_20_2.0_2.0']:,.2f}\nSMA 20: {last_row['SMA_20']:,.2f}\nEMA 20: {last_row['EMA_20']:,.2f}"
        SimpleTradeSignal = ""
        #simple trade signal
        for strategy in self.strategies:
            simple_prompt = strategy.generate_signal(self.symbol, df)
            prompts += simple_prompt
            logger.info(f"Strategy: {strategy.name}, Signal: {simple_prompt}")
        logger.info("--------------Simple Prompt End------------------")
        return prompts