# src/LangTrader/ai/strategies/bollinger_strategy.py
from src.LangTrader.ai.strategies.base_strategy import BaseStrategy

class BollingerStrategy(BaseStrategy):
    """布林带策略"""
    
    def __init__(self, period: int = 20, std_dev: float = 2.0):
        super().__init__("布林带策略", "基于布林带的突破和回归策略")
        self.period = period
        self.std_dev = std_dev
    
    def generate_signal(self, market_data: dict, position_data: dict) -> dict:
        """生成布林带交易信号"""
        best_signal = {'action': 'HOLD', 'confidence': 0.0, 'side': 'none', 'leverage': 1, 'reason': '无明确信号'}
        
        for symbol, indicators in market_data.items():
            # 获取布林带指标
            upper_band = indicators.get('BBU_20_2.0_2.0')  # 上轨
            middle_band = indicators.get('BBB_20_2.0_2.0')  # 中轨
            lower_band = indicators.get('BBP_20_2.0_2.0')  # 下轨
            close_price = indicators.get('close')  # 收盘价
            
            # 检查数据完整性
            if None in [upper_band, middle_band, lower_band, close_price]:
                continue
                
            try:
                upper_band = float(upper_band)
                middle_band = float(middle_band)
                lower_band = float(lower_band)
                close_price = float(close_price)
            except (ValueError, TypeError):
                continue
            
            # 价格触及下轨，可能反弹，考虑买入
            if close_price <= lower_band:
                confidence = min(1.0, (middle_band - close_price) / (middle_band - lower_band))
                if confidence > best_signal['confidence']:
                    best_signal = {
                        'action': 'BUY',
                        'confidence': confidence,
                        'side': 'long',
                        'leverage': 2,
                        'reason': f'{symbol} 价格触及布林带下轨，可能反弹'
                    }
            # 价格触及上轨，可能回调，考虑卖出
            elif close_price >= upper_band:
                confidence = min(1.0, (close_price - middle_band) / (upper_band - middle_band))
                if confidence > best_signal['confidence']:
                    best_signal = {
                        'action': 'SELL',
                        'confidence': confidence,
                        'side': 'short',
                        'leverage': 2,
                        'reason': f'{symbol} 价格触及布林带上轨，可能回调'
                    }
        
        return best_signal