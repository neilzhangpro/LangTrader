#!/usr/bin/env python3
"""
Unit tests for IndicatorCalculator
Tests technical indicator calculations
"""
import sys
from pathlib import Path
import pytest

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.services.indicators import IndicatorCalculator, Kline, ohlcv_to_klines


class TestOhlcvConversion:
    """Test OHLCV to Kline conversion"""
    
    def test_ohlcv_to_klines(self, sample_ohlcv_data):
        """Test converting OHLCV data to Kline objects"""
        klines = ohlcv_to_klines(sample_ohlcv_data[:10])
        
        assert len(klines) == 10
        assert isinstance(klines[0], Kline)
        assert klines[0].open == sample_ohlcv_data[0][1]
        assert klines[0].close == sample_ohlcv_data[0][4]
    
    def test_ohlcv_to_klines_empty(self):
        """Test converting empty data"""
        klines = ohlcv_to_klines([])
        
        assert klines == []


class TestEMACalculation:
    """Test EMA calculation"""
    
    def test_calculate_ema_20(self, sample_klines):
        """Test EMA 20 calculation"""
        ema = IndicatorCalculator.calculate_ema(sample_klines, period=20)
        
        assert ema > 0
        # EMA should be close to recent prices
        last_close = sample_klines[-1].close
        assert abs(ema - last_close) < last_close * 0.2  # Within 20%
    
    def test_calculate_ema_50(self, sample_klines):
        """Test EMA 50 calculation"""
        ema = IndicatorCalculator.calculate_ema(sample_klines, period=50)
        
        assert ema > 0
    
    def test_calculate_ema_insufficient_data(self, sample_klines):
        """Test EMA with insufficient data"""
        short_klines = sample_klines[:5]  # Only 5 candles
        ema = IndicatorCalculator.calculate_ema(short_klines, period=20)
        
        assert ema == 0.0


class TestMACDCalculation:
    """Test MACD calculation"""
    
    def test_calculate_macd(self, sample_klines):
        """Test MACD calculation"""
        macd = IndicatorCalculator.calculate_macd(sample_klines)
        
        # MACD can be positive or negative
        assert isinstance(macd, float)
    
    def test_calculate_macd_insufficient_data(self, sample_klines):
        """Test MACD with insufficient data"""
        short_klines = sample_klines[:20]  # Less than 26
        macd = IndicatorCalculator.calculate_macd(short_klines)
        
        assert macd == 0.0


class TestRSICalculation:
    """Test RSI calculation"""
    
    def test_calculate_rsi(self, sample_klines):
        """Test RSI calculation"""
        rsi = IndicatorCalculator.calculate_rsi(sample_klines, period=7)
        
        # RSI is between 0 and 100
        assert 0 <= rsi <= 100
    
    def test_calculate_rsi_14(self, sample_klines):
        """Test RSI with 14 period"""
        rsi = IndicatorCalculator.calculate_rsi(sample_klines, period=14)
        
        assert 0 <= rsi <= 100
    
    def test_calculate_rsi_insufficient_data(self, sample_klines):
        """Test RSI with insufficient data"""
        short_klines = sample_klines[:5]
        rsi = IndicatorCalculator.calculate_rsi(short_klines, period=14)
        
        assert rsi == 0.0


class TestATRCalculation:
    """Test ATR calculation"""
    
    def test_calculate_atr(self, sample_klines):
        """Test ATR calculation"""
        atr = IndicatorCalculator.calculate_atr(sample_klines, period=14)
        
        assert atr > 0
    
    def test_calculate_atr3(self, sample_klines):
        """Test ATR 3-period for short term volatility"""
        atr = IndicatorCalculator.calculate_atr3(sample_klines)
        
        assert atr > 0
    
    def test_calculate_atr_percent(self, sample_klines):
        """Test ATR as percentage of price"""
        atr_pct = IndicatorCalculator.calculate_atr_percent(sample_klines, period=14)
        
        assert atr_pct > 0
        assert atr_pct < 100  # Should be reasonable percentage
    
    def test_calculate_atr_insufficient_data(self, sample_klines):
        """Test ATR with insufficient data"""
        short_klines = sample_klines[:10]
        atr = IndicatorCalculator.calculate_atr(short_klines, period=14)
        
        assert atr == 0.0


class TestBollingerBands:
    """Test Bollinger Bands calculation"""
    
    def test_calculate_bollinger_bands(self, sample_klines):
        """Test Bollinger Bands calculation"""
        bb = IndicatorCalculator.calculate_bollinger_bands(sample_klines, period=20, std_dev=2.0)
        
        assert 'upper' in bb
        assert 'middle' in bb
        assert 'lower' in bb
        assert 'bandwidth' in bb
        assert 'percent_b' in bb
        
        # Upper > Middle > Lower
        assert bb['upper'] > bb['middle'] > bb['lower']
    
    def test_bollinger_bands_percent_b(self, sample_klines):
        """Test Bollinger %B calculation"""
        bb = IndicatorCalculator.calculate_bollinger_bands(sample_klines)
        
        # %B should be between -0.5 and 1.5 roughly
        assert -0.5 <= bb['percent_b'] <= 1.5
    
    def test_bollinger_insufficient_data(self, sample_klines):
        """Test Bollinger with insufficient data"""
        short_klines = sample_klines[:10]
        bb = IndicatorCalculator.calculate_bollinger_bands(short_klines, period=20)
        
        assert bb['upper'] == 0


class TestVWAP:
    """Test VWAP calculation"""
    
    def test_calculate_vwap(self, sample_klines):
        """Test VWAP calculation"""
        vwap = IndicatorCalculator.calculate_vwap(sample_klines)
        
        assert vwap > 0
        
        # VWAP should be close to average price
        avg_close = sum(k.close for k in sample_klines) / len(sample_klines)
        assert abs(vwap - avg_close) < avg_close * 0.3
    
    def test_calculate_vwap_empty(self):
        """Test VWAP with empty data"""
        vwap = IndicatorCalculator.calculate_vwap([])
        
        assert vwap == 0.0


class TestVolumeIndicators:
    """Test volume-based indicators"""
    
    def test_calculate_volume_ratio(self, sample_klines):
        """Test volume ratio calculation"""
        ratio = IndicatorCalculator.calculate_volume_ratio(sample_klines, period=20)
        
        assert ratio > 0
    
    def test_calculate_obv(self, sample_klines):
        """Test OBV calculation"""
        obv = IndicatorCalculator.calculate_obv(sample_klines)
        
        # OBV can be any value
        assert isinstance(obv, float)
    
    def test_calculate_volume_stats(self, sample_klines):
        """Test volume statistics"""
        stats = IndicatorCalculator.calculate_volume_stats(sample_klines)
        
        assert 'current_volume' in stats
        assert 'average_volume' in stats
        assert stats['current_volume'] > 0
        assert stats['average_volume'] > 0


class TestADX:
    """Test ADX calculation"""
    
    def test_calculate_adx(self, sample_klines):
        """Test ADX calculation"""
        adx = IndicatorCalculator.calculate_adx(sample_klines, period=14)
        
        assert 'adx' in adx
        assert 'plus_di' in adx
        assert 'minus_di' in adx
        
        # ADX is between 0 and 100
        assert 0 <= adx['adx'] <= 100
    
    def test_calculate_adx_insufficient_data(self, sample_klines):
        """Test ADX with insufficient data"""
        short_klines = sample_klines[:20]
        adx = IndicatorCalculator.calculate_adx(short_klines, period=14)
        
        assert adx['adx'] == 0


class TestStochastic:
    """Test Stochastic Oscillator calculation"""
    
    def test_calculate_stochastic(self, sample_klines):
        """Test Stochastic calculation"""
        stoch = IndicatorCalculator.calculate_stochastic(sample_klines, k_period=14, d_period=3)
        
        assert 'k' in stoch
        assert 'd' in stoch
        
        # Stochastic is between 0 and 100
        assert 0 <= stoch['k'] <= 100
        assert 0 <= stoch['d'] <= 100
    
    def test_stochastic_insufficient_data(self, sample_klines):
        """Test Stochastic with insufficient data"""
        short_klines = sample_klines[:10]
        stoch = IndicatorCalculator.calculate_stochastic(short_klines, k_period=14)
        
        assert stoch['k'] == 50  # Default value


class TestSeriesIndicators:
    """Test series (array) indicator calculations"""
    
    def test_calculate_series_indicators(self, sample_klines):
        """Test series indicators for historical analysis"""
        series = IndicatorCalculator.calculate_series_indicators(sample_klines)
        
        assert 'mid_prices' in series
        assert 'ema20_values' in series
        assert 'macd_values' in series
        assert 'rsi7_values' in series
        
        assert len(series['mid_prices']) == len(sample_klines)


class TestScoreCoins:
    """Test coin scoring function"""
    
    def test_score_bullish_indicators(self, sample_indicators):
        """Test scoring with bullish indicators"""
        # Bullish setup
        indicators = sample_indicators.copy()
        indicators['macd_3m'] = 0.5
        indicators['macd_4h'] = 0.3
        indicators['rsi_3m'] = 55
        indicators['rsi_4h'] = 60
        
        score = IndicatorCalculator.score_coins(indicators)
        
        # Should be above neutral (50)
        assert score > 50
        assert 0 <= score <= 100
    
    def test_score_bearish_indicators(self):
        """Test scoring with bearish indicators"""
        indicators = {
            'current_price': 95,
            'ema_3m': 100,
            'ema_4h': 105,
            'macd_3m': -0.5,
            'macd_4h': -0.3,
            'rsi_3m': 35,
            'rsi_4h': 40
        }
        
        score = IndicatorCalculator.score_coins(indicators)
        
        # Should be below neutral
        assert score < 50
    
    def test_score_bounds(self):
        """Test score is always 0-100"""
        # Extreme bearish
        indicators = {
            'current_price': 50,
            'ema_3m': 100,
            'ema_4h': 150,
            'macd_3m': -10,
            'macd_4h': -10,
            'rsi_3m': 10,
            'rsi_4h': 10
        }
        
        score = IndicatorCalculator.score_coins(indicators)
        assert 0 <= score <= 30  # Very low score for bearish
        
        # Extreme bullish
        indicators = {
            'current_price': 150,
            'ema_3m': 100,
            'ema_4h': 50,
            'macd_3m': 10,
            'macd_4h': 10,
            'rsi_3m': 55,
            'rsi_4h': 55
        }
        
        score = IndicatorCalculator.score_coins(indicators)
        assert 70 <= score <= 100  # High score for bullish


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_klines(self):
        """Test all indicators with empty data"""
        empty = []
        
        assert IndicatorCalculator.calculate_ema(empty, 20) == 0.0
        assert IndicatorCalculator.calculate_macd(empty) == 0.0
        assert IndicatorCalculator.calculate_rsi(empty, 7) == 0.0
        assert IndicatorCalculator.calculate_atr(empty, 14) == 0.0
        assert IndicatorCalculator.calculate_vwap(empty) == 0.0
        assert IndicatorCalculator.calculate_obv(empty) == 0.0
    
    def test_single_kline(self, sample_klines):
        """Test with only one candle"""
        single = sample_klines[:1]
        
        # Most indicators should return 0 or default
        assert IndicatorCalculator.calculate_ema(single, 20) == 0.0
        assert IndicatorCalculator.calculate_macd(single) == 0.0
        assert IndicatorCalculator.calculate_obv(single) == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

