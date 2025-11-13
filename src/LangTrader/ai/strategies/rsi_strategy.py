# src/LangTrader/ai/strategies/rsi_strategy.py
from src.LangTrader.ai.strategies.base_strategy import BaseStrategy

class RSIStrategy(BaseStrategy):
    """RSI超买超卖策略"""
    
    def __init__(self, rsi_period: int = 14, overbought: int = 70, oversold: int = 30):
        super().__init__("RSI策略", "基于RSI指标的超买超卖策略")
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
    
    def generate_signal(self, market_data: dict, position_data: dict) -> dict:
        """生成RSI交易信号"""
        # 假设market_data中包含各币种的指标数据
        signal_summary = ""
        best_signal = {'action': 'HOLD', 'confidence': 0.0, 'side': 'none', 'leverage': 1, 'reason': '无明确交易信号'}
        
        for symbol, indicators in market_data.items():
            rsi_value = indicators.get('RSI_14', 50)
            
            if rsi_value < self.oversold:
                confidence = min(1.0, (self.oversold - rsi_value) / self.oversold)
                if confidence > best_signal['confidence']:
                    best_signal = {
                        'action': 'BUY',
                        'confidence': confidence,
                        'side': 'long',
                        'leverage': 2,
                        'reason': f'{symbol} RSI超卖，当前值: {rsi_value:.2f}'
                    }
            elif rsi_value > self.overbought:
                confidence = min(1.0, (rsi_value - self.overbought) / (100 - self.overbought))
                if confidence > best_signal['confidence']:
                    best_signal = {
                        'action': 'SELL',
                        'confidence': confidence,
                        'side': 'short',
                        'leverage': 2,
                        'reason': f'{symbol} RSI超买，当前值: {rsi_value:.2f}'
                    }
        
        return best_signal