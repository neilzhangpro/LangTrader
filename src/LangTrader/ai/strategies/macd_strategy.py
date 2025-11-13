# src/LangTrader/ai/strategies/macd_strategy.py
from src.LangTrader.ai.strategies.base_strategy import BaseStrategy

class MACDStrategy(BaseStrategy):
    """MACD金叉死叉策略"""
    
    def __init__(self):
        super().__init__("MACD策略", "基于MACD指标的金叉死叉策略")
    
    def generate_signal(self, market_data: dict, position_data: dict) -> dict:
        """生成MACD交易信号"""
        best_signal = {'action': 'HOLD', 'confidence': 0.0, 'side': 'none', 'leverage': 1, 'reason': ''}
        
        for symbol, indicators in market_data.items():
            macd = indicators.get('MACD_12_26_9', 0)
            macd_signal = indicators.get('MACDs_12_26_9', 0)
            macd_hist = indicators.get('MACDh_12_26_9', 0)
            
            # 金叉信号
            if macd > macd_signal and macd_hist > 0:
                confidence = min(1.0, abs(macd_hist) * 10)
                if confidence > best_signal['confidence']:
                    best_signal = {
                        'action': 'BUY',
                        'confidence': confidence,
                        'side': 'long',
                        'leverage': 3,
                        'reason': f'{symbol} MACD金叉，柱状图: {macd_hist:.4f}'
                    }
            # 死叉信号
            elif macd < macd_signal and macd_hist < 0:
                confidence = min(1.0, abs(macd_hist) * 10)
                if confidence > best_signal['confidence']:
                    best_signal = {
                        'action': 'SELL',
                        'confidence': confidence,
                        'side': 'short',
                        'leverage': 3,
                        'reason': f'{symbol} MACD死叉，柱状图: {macd_hist:.4f}'
                    }
        
        return best_signal