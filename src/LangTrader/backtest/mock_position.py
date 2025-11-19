"""
模拟仓位管理器 - 在回测中模拟真实的持仓行为
"""
from typing import Dict, Optional, List
from datetime import datetime
from src.LangTrader.utils import logger

class MockPosition:
    """单个模拟持仓"""
    def __init__(
        self,
        symbol: str,
        side: str,  # 'long' or 'short'
        entry_price: float,
        quantity: float,
        leverage: int,
        stop_loss_percent: float = 0.05,
        take_profit_percent: float = 0.12,
        opened_at: datetime = None,
        strategy_name: str = None
    ):
        self.symbol = symbol
        self.side = side.lower()
        self.entry_price = entry_price
        self.quantity = quantity
        self.leverage = leverage
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.opened_at = opened_at or datetime.now()
        self.strategy_name = strategy_name
        
        # 计算止损止盈价格
        if self.side == 'long':
            self.stop_loss_price = entry_price * (1 - stop_loss_percent)
            self.take_profit_price = entry_price * (1 + take_profit_percent)
        else:  # short
            self.stop_loss_price = entry_price * (1 + stop_loss_percent)
            self.take_profit_price = entry_price * (1 - take_profit_percent)
        
        # 持仓状态
        self.exit_price = None
        self.exit_reason = None
        self.closed_at = None
        self.realized_pnl = None
        self.pnl_percent = None
    
    def calculate_pnl(self, current_price: float) -> Dict:
        """计算当前盈亏"""
        if self.side == 'long':
            price_change = current_price - self.entry_price
        else:  # short
            price_change = self.entry_price - current_price
        
        # PnL = 价格变化 * 数量 * 杠杆
        pnl = price_change * self.quantity * self.leverage
        pnl_percent = (price_change / self.entry_price) * self.leverage
        
        return {
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'current_price': current_price
        }
    
    def check_stop_conditions(self, current_price: float) -> Optional[str]:
        """检查是否触发止损/止盈"""
        if self.side == 'long':
            if current_price <= self.stop_loss_price:
                return 'stop_loss'
            elif current_price >= self.take_profit_price:
                return 'take_profit'
        else:  # short
            if current_price >= self.stop_loss_price:
                return 'stop_loss'
            elif current_price <= self.take_profit_price:
                return 'take_profit'
        return None
    
    def close(self, exit_price: float, exit_reason: str, closed_at: datetime = None):
        """平仓"""
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.closed_at = closed_at or datetime.now()
        
        pnl_info = self.calculate_pnl(exit_price)
        self.realized_pnl = pnl_info['pnl']
        self.pnl_percent = pnl_info['pnl_percent']
        
        logger.info(
            f"平仓 {self.symbol} {self.side.upper()}: "
            f"入场${self.entry_price:.2f} → 出场${exit_price:.2f}, "
            f"PnL={self.realized_pnl:+.2f} ({self.pnl_percent:+.2%}), "
            f"原因: {exit_reason}"
        )
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'leverage': self.leverage,
            'stop_loss_price': self.stop_loss_price,
            'take_profit_price': self.take_profit_price,
            'realized_pnl': self.realized_pnl,
            'pnl_percent': self.pnl_percent,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'exit_reason': self.exit_reason,
            'strategy_name': self.strategy_name
        }


class MockPositionManager:
    """模拟仓位管理器 - 管理多个持仓"""
    def __init__(self, initial_balance: float, risk_config: Dict):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_config = risk_config
        
        # 持仓记录
        self.open_positions: Dict[str, MockPosition] = {}  # {symbol: position}
        self.closed_positions: List[MockPosition] = []
        
        # 资金曲线
        self.equity_curve = []
    
    def can_open_position(self, symbol: str) -> bool:
        """检查是否可以开仓"""
        # 1. 检查是否已有该币种持仓
        if symbol in self.open_positions:
            logger.warning(f"{symbol} 已存在持仓，不能重复开仓")
            return False
        
        # 2. 检查可用余额
        if self.current_balance < 10:
            logger.warning("余额不足，无法开仓")
            return False
        
        # 3. 检查持仓数量限制（可选）
        max_positions = self.risk_config.get('max_concurrent_positions', 5)
        if len(self.open_positions) >= max_positions:
            logger.warning(f"已达到最大持仓数量 {max_positions}")
            return False
        
        return True
    
    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        leverage: int,
        opened_at: datetime,
        strategy_name: str = None
    ) -> Optional[MockPosition]:
        """开仓"""
        if not self.can_open_position(symbol):
            return None
        
        # 计算开仓数量（使用固定比例资金）
        position_size_ratio = self.risk_config.get('position_size_ratio', 0.1)  # 10%
        position_value = self.current_balance * position_size_ratio
        quantity = position_value / entry_price
        
        # 创建持仓
        position = MockPosition(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            leverage=leverage,
            stop_loss_percent=self.risk_config.get('stop_loss_percent', 0.05),
            take_profit_percent=self.risk_config.get('take_profit_percent', 0.12),
            opened_at=opened_at,
            strategy_name=strategy_name
        )
        
        self.open_positions[symbol] = position
        
        logger.info(
            f"开仓 {symbol} {side.upper()}: "
            f"价格=${entry_price:.2f}, 数量={quantity:.4f}, "
            f"杠杆={leverage}x, 名义价值=${position_value:.2f}"
        )
        
        return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str,
        closed_at: datetime
    ) -> Optional[MockPosition]:
        """平仓"""
        if symbol not in self.open_positions:
            logger.warning(f"{symbol} 不存在开仓记录")
            return None
        
        position = self.open_positions.pop(symbol)
        position.close(exit_price, exit_reason, closed_at)
        
        # 更新余额
        self.current_balance += position.realized_pnl
        
        self.closed_positions.append(position)
        return position
    
    def update_positions(self, market_prices: Dict[str, float], current_time: datetime):
        """
        更新所有持仓状态，检查止损止盈
        
        Args:
            market_prices: {symbol: current_price}
            current_time: 当前时间
        """
        symbols_to_close = []
        
        for symbol, position in self.open_positions.items():
            if symbol not in market_prices:
                continue
            
            current_price = market_prices[symbol]
            
            # 检查止损止盈
            stop_reason = position.check_stop_conditions(current_price)
            if stop_reason:
                symbols_to_close.append((symbol, current_price, stop_reason))
        
        # 触发平仓
        for symbol, exit_price, exit_reason in symbols_to_close:
            self.close_position(symbol, exit_price, exit_reason, current_time)
    
    def close_all_positions(self, market_prices: Dict[str, float], current_time: datetime):
        """强制平掉所有持仓（回测结束时）"""
        symbols = list(self.open_positions.keys())
        for symbol in symbols:
            if symbol in market_prices:
                self.close_position(
                    symbol,
                    market_prices[symbol],
                    'backtest_end',
                    current_time
                )
    
    def record_equity(self, market_prices: Dict[str, float], timestamp: datetime):
        """记录资金曲线"""
        # 计算总权益 = 当前余额 + 未平仓浮动盈亏
        total_equity = self.current_balance
        
        for symbol, position in self.open_positions.items():
            if symbol in market_prices:
                pnl_info = position.calculate_pnl(market_prices[symbol])
                total_equity += pnl_info['pnl']
        
        self.equity_curve.append({
            'timestamp': timestamp.isoformat(),
            'balance': self.current_balance,
            'equity': total_equity,
            'open_positions': len(self.open_positions)
        })
    
    def get_position_info(self, symbol: str, market_prices: Dict[str, float]) -> Optional[Dict]:
        """获取持仓信息（用于LLM决策）"""
        if symbol not in self.open_positions:
            return None
        
        position = self.open_positions[symbol]
        current_price = market_prices.get(symbol, position.entry_price)
        pnl_info = position.calculate_pnl(current_price)
        
        return {
            'symbol': symbol,
            'side': position.side,
            'entry_price': position.entry_price,
            'current_price': current_price,
            'quantity': position.quantity,
            'leverage': position.leverage,
            'pnl': pnl_info['pnl'],
            'pnl_percentage': pnl_info['pnl_percent'],
            'stop_loss_price': position.stop_loss_price,
            'take_profit_price': position.take_profit_price,
            'opened_at': position.opened_at
        }