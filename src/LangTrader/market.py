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

    def get_simple_trade_signal(self, df):
        """生成清晰的策略信号摘要"""
        
        last_row = df.iloc[-1]
        
        # 基础数据
        base_info = f"""
    当前币种: {self.symbol}
    当前价格: ${last_row['close']:,.2f}
    24H最高: ${last_row['high']:,.2f}
    24H最低: ${last_row['low']:,.2f}
    24H成交量: {last_row['volume']:,.2f}
    """
        
        # 关键指标
        key_indicators = f"""
    【关键指标】
    - RSI(14): {last_row.get('RSI_14', 0):.1f} {'(超买)' if last_row.get('RSI_14', 50) > 70 else '(超卖)' if last_row.get('RSI_14', 50) < 30 else '(中性)'}
    - MACD: {'金叉' if last_row.get('MACD_12_26_9', 0) > last_row.get('MACDs_12_26_9', 0) else '死叉'}
    - 布林带位置: {'上轨外' if last_row['close'] > last_row.get('BBU_20_2.0_2.0', 999999) else '下轨外' if last_row['close'] < last_row.get('BBL_20_2.0_2.0', 0) else '轨道内'}
    - 均线趋势: {'多头' if last_row['close'] > last_row.get('SMA_20', 0) else '空头'}
    """
        
        # 收集策略信号（简化输出）
        strategy_signals = "\n【各策略信号】"
        for strategy in self.strategies:
            try:
                signal = strategy.generate_signal(self.symbol, df)
                # 简化信号描述
                if signal:
                    strategy_signals += f"\n• {strategy.name}: {signal.strip()}"
            except Exception as e:
                logger.error(f"策略 {strategy.name} 失败: {e}")
        
        # 组合
        return base_info + key_indicators + strategy_signals