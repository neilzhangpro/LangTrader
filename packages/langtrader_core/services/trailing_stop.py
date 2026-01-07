# packages/langtrader_core/services/trailing_stop.py
"""
追踪止损服务
Trailing Stop Service

当持仓盈利超过阈值后，自动上移止损位锁定利润。

使用方法：
1. 在 bot.risk_limits 中配置追踪止损参数
2. 在 execution 节点每个周期调用 check_and_update()
3. 如果 should_close_position() 返回 True，执行平仓
"""
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from langtrader_core.graph.state import Position
from langtrader_core.utils import get_logger

logger = get_logger("trailing_stop")


@dataclass
class TrailingStopState:
    """单个持仓的追踪止损状态"""
    symbol: str
    peak_pnl_pct: float = 0.0  # 历史最高盈利百分比
    trailing_sl: Optional[float] = None  # 当前追踪止损价格
    activated: bool = False  # 是否已激活追踪


class TrailingStopManager:
    """
    追踪止损管理器
    
    逻辑：
    1. 持仓盈利 >= trailing_stop_trigger_pct 时激活追踪
    2. 止损位设为：当前价格 * (1 - trailing_stop_distance_pct) (多头)
    3. 止损位只会向盈利方向移动，不会回退
    4. 价格触及止损位时触发平仓
    
    配置参数 (从 bot.risk_limits 读取)：
    - trailing_stop_enabled: 是否启用追踪止损
    - trailing_stop_trigger_pct: 触发追踪的最小盈利 (默认 3%)
    - trailing_stop_distance_pct: 追踪距离 (默认 1.5%)
    - trailing_stop_lock_profit_pct: 最少锁定利润 (默认 1%)
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化追踪止损管理器
        
        Args:
            config: 追踪止损配置 (从 bot.risk_limits 读取)
        """
        config = config or {}
        
        self.enabled = config.get('trailing_stop_enabled', False)
        self.trigger_pct = config.get('trailing_stop_trigger_pct', 3.0)  # 触发阈值 3%
        self.distance_pct = config.get('trailing_stop_distance_pct', 1.5)  # 追踪距离 1.5%
        self.lock_profit_pct = config.get('trailing_stop_lock_profit_pct', 1.0)  # 最少锁定 1%
        
        # 每个持仓的追踪状态
        self._states: Dict[str, TrailingStopState] = {}
        
        if self.enabled:
            logger.info(
                f"📊 TrailingStopManager initialized: "
                f"trigger={self.trigger_pct}%, distance={self.distance_pct}%, "
                f"lock={self.lock_profit_pct}%"
            )
    
    def _get_or_create_state(self, symbol: str) -> TrailingStopState:
        """获取或创建持仓的追踪状态"""
        if symbol not in self._states:
            self._states[symbol] = TrailingStopState(symbol=symbol)
        return self._states[symbol]
    
    def _calculate_pnl_pct(self, position: Position, current_price: float) -> float:
        """
        计算持仓的未实现盈亏百分比
        
        Args:
            position: 持仓信息
            current_price: 当前价格
            
        Returns:
            盈亏百分比 (正为盈利，负为亏损)
        """
        entry_price = position.price
        if entry_price <= 0:
            return 0.0
        
        if position.side == 'buy':  # 多头
            return (current_price - entry_price) / entry_price * 100
        else:  # 空头
            return (entry_price - current_price) / entry_price * 100
    
    def calculate_trailing_stop(
        self, 
        position: Position, 
        current_price: float
    ) -> Optional[float]:
        """
        计算追踪止损价格
        
        Args:
            position: 持仓信息
            current_price: 当前价格
            
        Returns:
            新的止损价格，如果不需要更新则返回 None
        """
        if not self.enabled or current_price <= 0:
            return None
        
        symbol = position.symbol
        entry_price = position.price
        state = self._get_or_create_state(symbol)
        
        # 计算当前盈亏百分比
        pnl_pct = self._calculate_pnl_pct(position, current_price)
        
        # 未达到触发阈值
        if pnl_pct < self.trigger_pct:
            return None
        
        # 首次激活
        if not state.activated:
            state.activated = True
            logger.info(f"🎯 {symbol} Trailing Stop ACTIVATED at {pnl_pct:+.2f}% profit")
        
        # 更新峰值盈利
        if pnl_pct > state.peak_pnl_pct:
            state.peak_pnl_pct = pnl_pct
        
        # 计算追踪止损价格
        if position.side == 'buy':  # 多头
            # 止损位 = 当前价格 * (1 - 追踪距离%)
            new_sl = current_price * (1 - self.distance_pct / 100)
            
            # 确保至少锁定 lock_profit_pct 的利润
            min_sl = entry_price * (1 + self.lock_profit_pct / 100)
            new_sl = max(new_sl, min_sl)
            
            # 止损只能向上移动（锁定更多利润）
            current_sl = state.trailing_sl or 0
            if new_sl > current_sl:
                old_sl = state.trailing_sl
                state.trailing_sl = new_sl
                logger.info(
                    f"📈 {symbol} Trailing Stop Updated: "
                    f"${old_sl:.4f if old_sl else 0:.4f} → ${new_sl:.4f} "
                    f"(PnL: {pnl_pct:+.2f}%, Peak: {state.peak_pnl_pct:.2f}%)"
                )
                return new_sl
        else:  # 空头
            # 止损位 = 当前价格 * (1 + 追踪距离%)
            new_sl = current_price * (1 + self.distance_pct / 100)
            
            # 确保至少锁定 lock_profit_pct 的利润
            max_sl = entry_price * (1 - self.lock_profit_pct / 100)
            new_sl = min(new_sl, max_sl)
            
            # 止损只能向下移动（锁定更多利润）
            current_sl = state.trailing_sl or float('inf')
            if new_sl < current_sl:
                old_sl = state.trailing_sl
                state.trailing_sl = new_sl
                logger.info(
                    f"📉 {symbol} Trailing Stop Updated: "
                    f"${old_sl:.4f if old_sl else 'inf'} → ${new_sl:.4f} "
                    f"(PnL: {pnl_pct:+.2f}%, Peak: {state.peak_pnl_pct:.2f}%)"
                )
                return new_sl
        
        return None
    
    def should_close_position(
        self, 
        position: Position, 
        current_price: float
    ) -> bool:
        """
        检查是否应该触发追踪止损平仓
        
        Args:
            position: 持仓信息
            current_price: 当前价格
            
        Returns:
            是否应该平仓
        """
        if not self.enabled or current_price <= 0:
            return False
        
        symbol = position.symbol
        state = self._states.get(symbol)
        
        if state is None or state.trailing_sl is None or not state.activated:
            return False
        
        trailing_sl = state.trailing_sl
        
        if position.side == 'buy':  # 多头
            if current_price <= trailing_sl:
                pnl_pct = self._calculate_pnl_pct(position, current_price)
                logger.warning(
                    f"🛑 {symbol} TRAILING STOP HIT! "
                    f"Price ${current_price:.4f} <= SL ${trailing_sl:.4f} "
                    f"(Final PnL: {pnl_pct:+.2f}%, Peak: {state.peak_pnl_pct:.2f}%)"
                )
                return True
        else:  # 空头
            if current_price >= trailing_sl:
                pnl_pct = self._calculate_pnl_pct(position, current_price)
                logger.warning(
                    f"🛑 {symbol} TRAILING STOP HIT! "
                    f"Price ${current_price:.4f} >= SL ${trailing_sl:.4f} "
                    f"(Final PnL: {pnl_pct:+.2f}%, Peak: {state.peak_pnl_pct:.2f}%)"
                )
                return True
        
        return False
    
    def check_positions(
        self, 
        positions: List[Position], 
        market_data: Dict[str, Dict[str, Any]]
    ) -> List[Tuple[Position, str]]:
        """
        检查所有持仓，返回需要平仓的列表
        
        Args:
            positions: 持仓列表
            market_data: 市场数据 {symbol: {indicators: {current_price: ...}}}
            
        Returns:
            需要平仓的列表 [(position, close_action), ...]
        """
        if not self.enabled:
            return []
        
        to_close = []
        
        for position in positions:
            symbol = position.symbol
            
            # 获取当前价格
            data = market_data.get(symbol, {})
            indicators = data.get('indicators', {})
            current_price = indicators.get('current_price', 0)
            
            if current_price <= 0:
                # ⚠️ 警告：没有实时价格数据，止盈/止损策略将无法正确计算 PnL
                # 这种情况通常发生在持仓币种不在 coins_pick 选出的列表中
                # 使用入场价作为回退（导致 PnL 为 0）
                logger.warning(
                    f"⚠️ {symbol}: No realtime price in market_data! "
                    f"Trailing stop may not work correctly. "
                    f"entry_price={position.price:.6f}"
                )
                # 不使用 position.price 作为 fallback，因为这会导致 PnL 始终为 0
                # 市场数据应该在 market_state 节点中已经补充
                continue
            
            # 先更新追踪止损位
            self.calculate_trailing_stop(position, current_price)
            
            # 检查是否触发止损
            if self.should_close_position(position, current_price):
                close_action = "close_long" if position.side == 'buy' else "close_short"
                to_close.append((position, close_action))
        
        return to_close
    
    def clear_position(self, symbol: str):
        """
        清除已平仓的持仓记录
        
        Args:
            symbol: 币种符号
        """
        if symbol in self._states:
            state = self._states[symbol]
            logger.info(
                f"🧹 Cleared trailing stop state for {symbol} "
                f"(Peak PnL: {state.peak_pnl_pct:.2f}%)"
            )
            del self._states[symbol]
    
    def get_state(self, symbol: str) -> Optional[TrailingStopState]:
        """获取指定持仓的追踪状态"""
        return self._states.get(symbol)
    
    def get_all_states(self) -> Dict[str, TrailingStopState]:
        """获取所有追踪状态"""
        return self._states.copy()

