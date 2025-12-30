# indicators calculation - 纯指标计算模块
# 不负责数据获取，只提供静态计算方法

from typing import List, Optional
from langtrader_core.utils import get_logger
from dataclasses import dataclass
import pandas as pd
import pandas_ta as ta

logger = get_logger("indicators")


@dataclass
class Kline:
    """K线数据"""
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades: int


def ohlcv_to_klines(ohlcv_data: List[list]) -> List[Kline]:
    """
    将 CCXT OHLCV 数据转换为 Kline 对象列表
    CCXT 格式: [timestamp, open, high, low, close, volume]
    """
    if not ohlcv_data:
        return []
    return [
        Kline(
            open_time=k[0], open=k[1], high=k[2], low=k[3],
            close=k[4], volume=k[5], close_time=k[0],
            quote_volume=0.0, trades=0
        ) for k in ohlcv_data
    ]


class IndicatorCalculator:
    """
    纯技术指标计算器
    所有计算方法都是静态方法，不依赖任何外部服务
    """
    
    @staticmethod
    def score_coins(indicators: dict) -> int:
        """
        根据指标评分
        
        Args:
            indicators: 包含以下字段的字典
                - current_price, ema_3m, ema_4h, macd_3m, macd_4h, rsi_3m, rsi_4h
                
        Returns:
            0-100 的评分
        """
        score = 50  # Base score
        
        current_price = indicators.get('current_price', 0)
        
        # Compare current price with the EMA 3m
        if current_price > indicators.get('ema_3m', 0):
            score += 10
        else:
            score -= 10
        
        # Compare current price with the EMA 4h
        if current_price > indicators.get('ema_4h', 0):
            score += 10
        else:
            score -= 10
        
        # Compare current price with the MACD 3m
        if current_price > indicators.get('macd_3m', 0):
            score += 10
        else:
            score -= 10

        # MACD 3m should be positive
        if indicators.get('macd_3m', 0) > 0:
            score += 10
        else:
            score -= 10
        
        # MACD 4h should be positive
        if indicators.get('macd_4h', 0) > 0:
            score += 15
        else:
            score -= 15
        
        # RSI 3m should between 30 and 70
        rsi_3m = indicators.get('rsi_3m', 50)
        if 30 < rsi_3m < 70:
            score += 5
        
        # RSI 4h should between 30 and 70
        rsi_4h = indicators.get('rsi_4h', 50)
        if 30 < rsi_4h < 70:
            score += 5
      
        return max(0, min(100, score))
        
    @staticmethod
    def calculate_ema(klines: List[Kline], period: int) -> float:
        """计算 EMA"""
        if len(klines) < period:
            return 0.0
        
        df = pd.DataFrame([{
            'close': k.close,
            'open': k.open,
            'high': k.high,
            'low': k.low,
            'volume': k.volume
        } for k in klines])
        
        ema = ta.ema(df['close'], length=period)
        return float(ema.iloc[-1]) if not ema.empty else 0.0
    
    @staticmethod
    def calculate_macd(klines: List[Kline]) -> float:
        """计算 MACD"""
        if len(klines) < 26:
            return 0.0
        
        df = pd.DataFrame([k.close for k in klines], columns=['close'])
        macd = ta.macd(df['close'])
        if macd is None or macd.empty:
            return 0.0
        if 'MACD_12_26_9' not in macd.columns:
            return 0.0
        return float(macd['MACD_12_26_9'].iloc[-1])
    
    @staticmethod
    def calculate_rsi(klines: List[Kline], period: int = 7) -> float:
        """计算 RSI"""
        if len(klines) <= period:
            return 0.0
        
        df = pd.DataFrame([k.close for k in klines], columns=['close'])
        rsi = ta.rsi(df['close'], length=period)
        if rsi is None or rsi.empty:
            return 0.0
        return float(rsi.iloc[-1])
    
    @staticmethod
    def calculate_atr(klines: List[Kline], period: int = 14) -> float:
        """计算 ATR"""
        if len(klines) <= period:
            return 0.0
        
        df = pd.DataFrame([{
            'high': k.high,
            'low': k.low,
            'close': k.close
        } for k in klines])
        
        atr = ta.atr(df['high'], df['low'], df['close'], length=period)
        if atr is None or atr.empty:
            return 0.0
        return float(atr.iloc[-1])
    
    @staticmethod
    def calculate_atr3(klines: List[Kline]) -> float:
        """计算 ATR（3周期）- 用于4小时K线的短期波动率"""
        return IndicatorCalculator.calculate_atr(klines, period=3)
    
    @staticmethod
    def calculate_volume_stats(klines: List[Kline]) -> dict:
        """计算成交量统计（当前成交量和平均成交量）"""
        if not klines:
            return {
                'current_volume': 0.0,
                'average_volume': 0.0
            }
        
        df = pd.DataFrame([{
            'volume': k.volume
        } for k in klines])
        
        current_volume = float(df['volume'].iloc[-1]) if len(df) > 0 else 0.0
        average_volume = float(df['volume'].mean()) if len(df) > 0 else 0.0
        
        return {
            'current_volume': current_volume,
            'average_volume': average_volume
        }
    
    @staticmethod
    def calculate_series_indicators(klines: List[Kline], periods: List[int] = None) -> dict:
        """计算序列指标（用于历史分析）"""
        if periods is None:
            periods = [7, 14, 20]
        
        df = pd.DataFrame([{
            'close': k.close,
            'high': k.high,
            'low': k.low,
            'volume': k.volume
        } for k in klines])
        
        result = {
            'mid_prices': df['close'].tolist(),
            'ema20_values': ta.ema(df['close'], length=20).tolist() if len(klines) >= 20 else [],
            'macd_values': ta.macd(df['close'])['MACD_12_26_9'].tolist() if len(klines) >= 26 else [],
            'rsi7_values': ta.rsi(df['close'], length=7).tolist() if len(klines) > 7 else [],
            'rsi14_values': ta.rsi(df['close'], length=14).tolist() if len(klines) > 14 else [],
        }
        
        return result

    @staticmethod
    def calculate_bollinger_bands(klines: List[Kline], period: int = 20, std_dev: float = 2.0) -> dict:
        """计算布林带"""
        if len(klines) < period:
            return {'upper': 0, 'middle': 0, 'lower': 0, 'bandwidth': 0, 'percent_b': 0}
        
        df = pd.DataFrame([k.close for k in klines], columns=['close'])
        bb = ta.bbands(df['close'], length=period, std=std_dev)
        
        if bb is None or bb.empty:
            return {'upper': 0, 'middle': 0, 'lower': 0, 'bandwidth': 0, 'percent_b': 0}
        
        # 动态获取列名（更稳妥的方式）
        bb_cols = bb.columns.tolist()
        upper_col = [c for c in bb_cols if c.startswith('BBU_')][0]
        middle_col = [c for c in bb_cols if c.startswith('BBM_')][0]
        lower_col = [c for c in bb_cols if c.startswith('BBL_')][0]
        
        upper = float(bb[upper_col].iloc[-1])
        middle = float(bb[middle_col].iloc[-1])
        lower = float(bb[lower_col].iloc[-1])
        current_price = klines[-1].close
        
        return {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'bandwidth': (upper - lower) / middle if middle else 0,
            'percent_b': (current_price - lower) / (upper - lower) if (upper - lower) else 0.5
        }

    
    @staticmethod
    def calculate_adx(klines: List[Kline], period: int = 14) -> dict:
        """计算ADX及方向指标"""
        if len(klines) < period * 2:
            return {'adx': 0, 'plus_di': 0, 'minus_di': 0}
        
        df = pd.DataFrame([{
            'high': k.high,
            'low': k.low,
            'close': k.close
        } for k in klines])
        
        adx = ta.adx(df['high'], df['low'], df['close'], length=period)
        
        if adx is None or adx.empty:
            return {'adx': 0, 'plus_di': 0, 'minus_di': 0}
        
        # 动态获取列名
        cols = adx.columns.tolist()
        adx_col = [c for c in cols if c.startswith('ADX_')][0]
        dmp_col = [c for c in cols if c.startswith('DMP_')][0]
        dmn_col = [c for c in cols if c.startswith('DMN_')][0]
        
        return {
            'adx': float(adx[adx_col].iloc[-1]),
            'plus_di': float(adx[dmp_col].iloc[-1]),
            'minus_di': float(adx[dmn_col].iloc[-1])
        }

    @staticmethod
    def calculate_vwap(klines: List[Kline]) -> float:
        """计算VWAP"""
        if not klines:
            return 0.0
        
        df = pd.DataFrame([{
            'high': k.high,
            'low': k.low,
            'close': k.close,
            'volume': k.volume
        } for k in klines])
        
        # 添加 DatetimeIndex 并排序（修复 VWAP 警告）
        df.index = pd.to_datetime([k.open_time for k in klines], unit='ms')
        df = df.sort_index()
        
        vwap = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
        
        if vwap is None or vwap.empty:
            return 0.0
        
        return float(vwap.iloc[-1])
    
    @staticmethod
    def calculate_volume_ratio(klines: List[Kline], period: int = 20) -> float:
        """计算当前成交量相对于平均成交量的比率"""
        if len(klines) < period + 1:
            return 1.0
        
        avg_volume = sum([k.volume for k in klines[-period-1:-1]]) / period
        current_volume = klines[-1].volume
        
        return current_volume / avg_volume if avg_volume > 0 else 1.0
    

    @staticmethod
    def calculate_stochastic(klines: List[Kline], k_period: int = 14, d_period: int = 3) -> dict:
        """计算随机指标"""
        if len(klines) < k_period:
            return {'k': 50, 'd': 50}
        
        df = pd.DataFrame([{
            'high': k.high,
            'low': k.low,
            'close': k.close
        } for k in klines])
        
        stoch = ta.stoch(df['high'], df['low'], df['close'], k=k_period, d=d_period)
        
        if stoch is None or stoch.empty:
            return {'k': 50, 'd': 50}
        
        # 动态获取列名
        cols = stoch.columns.tolist()
        k_col = [c for c in cols if c.startswith('STOCHk_')][0]
        d_col = [c for c in cols if c.startswith('STOCHd_')][0]
        
        return {
            'k': float(stoch[k_col].iloc[-1]),
            'd': float(stoch[d_col].iloc[-1])
        }
    
    @staticmethod
    def calculate_obv(klines: List[Kline]) -> float:
        """计算OBV"""
        if len(klines) < 2:
            return 0.0
        
        df = pd.DataFrame([{
            'close': k.close,
            'volume': k.volume
        } for k in klines])
        
        obv = ta.obv(df['close'], df['volume'])
        
        if obv is None or obv.empty:
            return 0.0
        
        return float(obv.iloc[-1])
    
    @staticmethod
    def calculate_atr_percent(klines: List[Kline], period: int = 14) -> float:
        """计算ATR百分比（相对于价格）"""
        if len(klines) <= period:
            return 0.0
        
        atr = IndicatorCalculator.calculate_atr(klines, period)
        current_price = klines[-1].close
        
        return (atr / current_price * 100) if current_price else 0.0
