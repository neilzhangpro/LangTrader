import requests
import pandas as pd
import pandas_ta as ta
from src.LangTrader.utils import logger

class CryptoFetcher:
    """This class is used to fetch data from exchange API"""
    def __init__(self, symbol:str = "ETH"):
        self.symbol = symbol
        self.exchange_base = "https://api.exchange.coinbase.com"
        self.data_base = "https://api.coinbase.com/v2"

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
        prompts += f"Current coin: {self.symbol}\nCurrent price: {last_row['close']:,.2f} USD\n24 hours highest price: {last_row['high']:,.2f} USD\n24 hours lowest price: {last_row['low']:,.2f} USD\n24 hours volume: {last_row['volume']:,.2f} ETH\nRSI: {last_row['RSI_14']:,.2f}\nMACD: {last_row['MACD_12_26_9']:,.2f}\nMACD Signal: {last_row['MACDs_12_26_9']:,.2f}\nMACD Hist: {last_row['MACDh_12_26_9']:,.2f}\nUpper Band: {last_row['BBU_20_2.0_2.0']:,.2f}\nMiddle Band: {last_row['BBB_20_2.0_2.0']:,.2f}\nLower Band: {last_row['BBP_20_2.0_2.0']:,.2f}\nSMA 20: {last_row['SMA_20']:,.2f}\nEMA 20: {last_row['EMA_20']:,.2f}"
        SimpleTradeSignal = ""
        #simple trade signal
        if last_row['RSI_14'] > 70:
                SimpleTradeSignal += "\nRSI greater than 70, sell signal"
        elif last_row['RSI_14'] < 30:
            SimpleTradeSignal += "\nRSI less than 30, buy signal"
        else:
            SimpleTradeSignal += "\nRSI between 30 and 70, hold signal"
        if last_row['MACD_12_26_9'] > last_row['MACDs_12_26_9']:
            SimpleTradeSignal += "\nMACD greater than MACD Signal, sell signal"
        elif last_row['MACD_12_26_9'] < last_row['MACDs_12_26_9']:
            SimpleTradeSignal += "\nMACD less than MACD Signal, buy signal"
        else:
            SimpleTradeSignal += "\nMACD equal to MACD Signal, hold signal"
        if last_row['BBU_20_2.0_2.0'] > last_row['close']:
            if last_row['BBU_20_2.0_2.0'] > last_row['BBP_20_2.0_2.0']:
                SimpleTradeSignal += "\nUpper band greater than current price, sell signal"
            else:
                SimpleTradeSignal += "\nUpper band and lower band between, hold signal"
        elif last_row['BBP_20_2.0_2.0'] < last_row['close']:
            if last_row['BBP_20_2.0_2.0'] < last_row['BBU_20_2.0_2.0']:
                SimpleTradeSignal += "\nLower band less than current price, buy signal"
            else:
                SimpleTradeSignal += "\nUpper band and lower band between, hold signal"
        else:
            SimpleTradeSignal += "\nUpper band and lower band between, hold signal"
        if last_row['SMA_20'] > last_row['close']:
            SimpleTradeSignal += "\nSMA greater than current price, sell signal"
        elif last_row['EMA_20'] < last_row['close']:
            SimpleTradeSignal += "\nEMA less than current price, buy signal"
        else:
            SimpleTradeSignal += "\nSMA and EMA between, hold signal"
        prompts += SimpleTradeSignal
        logger.info("--------------Simple Prompt End------------------")
        return prompts