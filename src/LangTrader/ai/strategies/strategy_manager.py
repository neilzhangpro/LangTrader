# src/LangTrader/ai/strategies/strategy_manager.py
from typing import Dict, List, Any
from src.LangTrader.ai.strategies.base_strategy import BaseStrategy

class StrategyManager:
    """策略管理器"""
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
    
    def register_strategy(self, strategy: BaseStrategy):
        """注册策略"""
        self.strategies[strategy.name] = strategy
    
    def get_strategy(self, name: str) -> BaseStrategy:
        """获取策略"""
        return self.strategies.get(name)
    
    def get_all_strategies(self) -> List[BaseStrategy]:
        """获取所有策略"""
        return list(self.strategies.values())
    
    def generate_all_signals(self, market_data: Dict[str, Any], position_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """生成所有策略的信号"""
        signals = {}
        for name, strategy in self.strategies.items():
            try:
                signal = strategy.generate_signal(market_data, position_data)
                signals[name] = signal
            except Exception as e:
                print(f"策略 {name} 生成信号失败: {e}")
                signals[name] = {
                    'action': 'HOLD',
                    'confidence': 0.0,
                    'side': 'none',
                    'leverage': 1,
                    'reason': f'策略执行失败: {e}'
                }
        return signals