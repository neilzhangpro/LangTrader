# packages/langtrader_core/services/risk_monitor.py
"""
动态风险监控服务
用于在交易执行前验证风险限制
"""
from typing import List, Optional, Dict, Any
from langtrader_core.graph.state import State, Position
from langtrader_core.data.repositories.trade_history import TradeHistoryRepository
from langtrader_core.utils import get_logger

logger = get_logger("risk_monitor")


class RiskMonitor:
    """动态风险监控"""
    
    def __init__(
        self,
        risk_limits: Dict[str, Any],
        trade_history_repo: Optional[TradeHistoryRepository] = None
    ):
        self.risk_limits = risk_limits
        self.trade_history_repo = trade_history_repo
    
    def calculate_total_exposure(
        self, 
        positions: List[Position],
        account_total: float
    ) -> float:
        """计算总风险敞口占比"""
        if account_total <= 0:
            return 0
        
        total_notional = sum(
            pos.amount * pos.price * getattr(pos, 'leverage', 1)
            for pos in positions
        )
        
        return total_notional / account_total
    
    def check_concentration(
        self,
        symbol: str,
        position_size: float,
        account_total: float
    ) -> bool:
        """检查单币种集中度"""
        max_single_pct = self.risk_limits.get('max_single_symbol_pct', 0.3)
        
        concentration = position_size / account_total if account_total > 0 else 0
        
        if concentration > max_single_pct:
            logger.warning(
                f"⚠️ {symbol}: Concentration {concentration*100:.1f}% "
                f"exceeds limit {max_single_pct*100:.1f}%"
            )
            return False
        
        return True
    
    def check_consecutive_losses(self, bot_id: int) -> bool:
        """检查连续亏损"""
        if not self.trade_history_repo:
            return True
        
        max_losses = self.risk_limits.get('max_consecutive_losses', 5)
        recent_trades = self.trade_history_repo.get_closed_trades(bot_id, limit=max_losses)
        
        if len(recent_trades) < max_losses:
            return True
        
        # 检查最近 N 笔是否全部亏损
        consecutive_losses = 0
        for trade in recent_trades:
            if trade.pnl_usd and float(trade.pnl_usd) < 0:
                consecutive_losses += 1
            else:
                break
        
        if consecutive_losses >= max_losses:
            logger.error(
                f"🚨 Consecutive losses detected: {consecutive_losses} trades"
            )
            return False
        
        return True
    
    def validate_new_position(
        self,
        state: State,
        symbol: str,
        position_size_usd: float
    ) -> Dict[str, Any]:
        """验证新开仓是否符合风险限制"""
        
        results = {
            "approved": True,
            "reasons": []
        }
        
        # 1. 检查总风险敞口
        account_total = state.account.total.get('USDT', 0) if state.account else 0
        
        if account_total > 0:
            current_exposure = self.calculate_total_exposure(
                state.positions, 
                account_total
            )
            max_exposure = self.risk_limits.get('max_total_exposure_pct', 0.8)
            
            # 预估新增敞口
            new_exposure = current_exposure + (position_size_usd / account_total)
            
            if new_exposure > max_exposure:
                results["approved"] = False
                results["reasons"].append(
                    f"Total exposure {new_exposure*100:.1f}% "
                    f"exceeds limit {max_exposure*100:.1f}%"
                )
        
        # 2. 检查单币种集中度
        if not self.check_concentration(symbol, position_size_usd, account_total):
            results["approved"] = False
            results["reasons"].append("Single symbol concentration too high")
        
        # 3. 检查连续亏损
        if not self.check_consecutive_losses(state.bot_id):
            results["approved"] = False
            results["reasons"].append(
                f"Consecutive losses limit reached, trading paused"
            )
        
        return results

