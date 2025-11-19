"""
历史数据获取器 - 使用yfinance获取数据
"""
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime
from typing import Dict, List
from src.LangTrader.utils import logger

class HistoricalDataFetcher:
    """获取历史K线数据用于回测"""
    
    def __init__(self, symbols: List[str], start_date: datetime, end_date: datetime):
        self.symbols = symbols
        self.start_date = start_date
        self.end_date = end_date
        self.historical_data: Dict[str, pd.DataFrame] = {}
    
    def _fetch_symbol_data(self, symbol: str, granularity: int) -> pd.DataFrame:
        """使用yfinance获取数据（适合主流币种）"""
        
        # yfinance 币种映射
        ticker_map = {
            'BTC': 'BTC-USD',
            'ETH': 'ETH-USD',
            'SOL': 'SOL-USD',
            'DOGE': 'DOGE-USD',
            'ADA': 'ADA-USD',
            'DOT': 'DOT-USD',
            'MATIC': 'MATIC-USD',
            'LINK': 'LINK-USD'
        }
        
        ticker = ticker_map.get(symbol, f'{symbol}-USD')
        
        # yfinance 时间间隔映射
        interval_map = {
            60: '1m',
            300: '5m',
            900: '15m',
            1800: '30m',
            3600: '1h',
            7200: '2h',
            14400: '4h',
            86400: '1d',
            604800: '1wk'
        }
        
        interval = interval_map.get(granularity, '1h')
        
        try:
            logger.info(f"正在下载 {ticker} 数据: {self.start_date.date()} 到 {self.end_date.date()}, 间隔={interval}")
            
            df = yf.download(
                ticker,
                start=self.start_date,
                end=self.end_date,
                interval=interval,
                progress=False,
                auto_adjust=True  # 自动调整价格
            )
            
            if df.empty:
                logger.warning(f"{symbol}: yfinance返回空数据")
                return None
            
            # 🔧 展平多层列索引（yfinance会返回MultiIndex）
            if isinstance(df.columns, pd.MultiIndex):
                # 只保留第一层列名
                df.columns = df.columns.get_level_values(0)
                logger.debug(f"{symbol} 展平列索引后: {df.columns.tolist()}")
            
            # 重命名列为小写
            df = df.rename(columns={
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            })
            
            # 重置索引，将日期列命名为time
            df = df.reset_index()
            if 'Date' in df.columns:
                df = df.rename(columns={'Date': 'time'})
            elif 'Datetime' in df.columns:
                df = df.rename(columns={'Datetime': 'time'})
            
            # 确保time列是datetime类型
            df['time'] = pd.to_datetime(df['time'])

            # 🔧 移除时区信息，转换为本地时间（修复时区问题）
            if df['time'].dt.tz is not None:
                df['time'] = df['time'].dt.tz_localize(None)

            logger.info(f"✅ {symbol}: 获取到 {len(df)} 条数据")
            
            # 计算技术指标
            df = self._calculate_indicators(df)
            
            return df
            
        except Exception as e:
            logger.error(f"yfinance获取{symbol}数据失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def fetch_all_data(self, granularity: int = 14400) -> Dict[str, pd.DataFrame]:
        """
        获取所有币种的历史数据
        
        Args:
            granularity: K线间隔（秒），默认14400=4小时
        
        Returns:
            {symbol: DataFrame}
        """
        logger.info(f"开始获取历史数据: {self.start_date} 到 {self.end_date}")
        
        for symbol in self.symbols:
            try:
                df = self._fetch_symbol_data(symbol, granularity)
                if df is not None and len(df) > 0:
                    self.historical_data[symbol] = df
                    logger.info(f"✅ {symbol}: 获取到 {len(df)} 条K线数据")
                else:
                    logger.warning(f"⚠️ {symbol}: 未获取到数据")
            except Exception as e:
                logger.error(f"❌ {symbol} 数据获取失败: {e}")
        
        return self.historical_data
    
    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标（复用market.py的逻辑）"""
        if len(df) < 50:
            logger.warning("数据不足50条，无法计算所有技术指标")
            return df
        
        try:
            logger.debug(f"开始计算技术指标，数据形状: {df.shape}, 列: {df.columns.tolist()}")
            
            # RSI
            rsi = ta.rsi(df["close"], length=14)
            if rsi is not None:
                df = pd.concat([df, rsi], axis=1)
                logger.debug(f"✅ RSI计算成功，列名: {rsi.name if hasattr(rsi, 'name') else 'unknown'}")
            else:
                logger.warning("⚠️ RSI计算返回None")
            
            # MACD
            macd = ta.macd(df["close"], fast=12, slow=26, signal=9)
            if macd is not None:
                df = pd.concat([df, macd], axis=1)
                logger.debug(f"✅ MACD计算成功，列: {macd.columns.tolist() if hasattr(macd, 'columns') else 'unknown'}")
            else:
                logger.warning("⚠️ MACD计算返回None")
            
            # 布林带
            bbands = ta.bbands(df["close"], length=20, std=2)
            if bbands is not None:
                df = pd.concat([df, bbands], axis=1)
                logger.debug(f"✅ 布林带计算成功")
            else:
                logger.warning("⚠️ 布林带计算返回None")
            
            # 均线
            sma_20 = ta.sma(df["close"], length=20)
            ema_20 = ta.ema(df["close"], length=20)
            if sma_20 is not None:
                df = pd.concat([df, sma_20], axis=1)
            if ema_20 is not None:
                df = pd.concat([df, ema_20], axis=1)
            
            # 成交量指标
            volume_sma = ta.sma(df["volume"], length=20)
            if volume_sma is not None:
                df['volume_sma_20'] = volume_sma
                df['volume_ratio'] = df["volume"] / df['volume_sma_20']
            
            volume_rsi = ta.rsi(df["volume"], length=14)
            if volume_rsi is not None:
                df['volume_rsi'] = volume_rsi
            
            logger.info(f"✅ 技术指标计算完成，最终列: {df.columns.tolist()}")
        
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return df
    
    def get_data_at_time(self, timestamp: datetime) -> Dict[str, pd.DataFrame]:
        """
        获取指定时间点之前的所有数据（模拟实盘只能看到历史）
        
        Returns:
            {symbol: DataFrame} - 每个币种截止到timestamp的数据
        """
        snapshot = {}
        
        for symbol, df in self.historical_data.items():
            # 只返回时间<=timestamp的数据
            mask = df['time'] <= timestamp
            snapshot[symbol] = df[mask].copy()
        
        return snapshot
    
    def get_current_prices(self, timestamp: datetime) -> Dict[str, float]:
        """获取指定时间的价格快照"""
        prices = {}
        
        for symbol, df in self.historical_data.items():
            # 找到最接近timestamp的K线
            mask = df['time'] <= timestamp
            if mask.any():
                latest_row = df[mask].iloc[-1]
                # 安全转换为float，避免Series警告
                close_val = latest_row['close']
                prices[symbol] = float(close_val.iloc[0]) if isinstance(close_val, pd.Series) else float(close_val)
        
        return prices