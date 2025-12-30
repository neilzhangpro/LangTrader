# packages/langtrader_core/backtest/mock_performance.py
"""
回测专用绩效服务（纯内存）
不依赖数据库，从 MockTrader 的交易记录计算指标
"""
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import numpy as np
from langtrader_core.services.performance import PerformanceMetrics
from langtrader_core.utils import get_logger

logger = get_logger("mock_performance")


@dataclass
class MockTrade:
    """回测交易记录"""
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    amount: float
    pnl_usd: float
    pnl_percent: float
    entry_time: int  # timestamp ms
    exit_time: int   # timestamp ms


class MockPerformanceService:
    """
    回测专用绩效服务
    
    特点：
    1. 纯内存操作，不依赖数据库
    2. 与 PerformanceService 接口兼容
    3. 实时记录 MockTrader 的交易
    """
    
    def __init__(self):
        self.trades: List[MockTrade] = []
    
    def record_trade(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        exit_price: float,
        amount: float,
        entry_time: int,
        exit_time: int
    ):
        """
        记录一笔已平仓交易
        
        Args:
            symbol: 交易对
            side: 开仓方向 ('buy' or 'sell')
            entry_price: 入场价
            exit_price: 出场价
            amount: 数量
            entry_time: 入场时间戳 (ms)
            exit_time: 出场时间戳 (ms)
        """
        # 计算盈亏
        if side == 'buy':
            pnl_usd = (exit_price - entry_price) * amount
            pnl_percent = ((exit_price - entry_price) / entry_price) * 100
        else:  # sell (short)
            pnl_usd = (entry_price - exit_price) * amount
            pnl_percent = ((entry_price - exit_price) / entry_price) * 100
        
        trade = MockTrade(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            amount=amount,
            pnl_usd=pnl_usd,
            pnl_percent=pnl_percent,
            entry_time=entry_time,
            exit_time=exit_time
        )
        
        self.trades.append(trade)
        
        emoji = "✅" if pnl_usd > 0 else "❌"
        logger.info(
            f"{emoji} Trade recorded: {symbol} {side} "
            f"PnL: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)"
        )
    
    def calculate_metrics(
        self, 
        bot_id: int = 0,  # 兼容接口，回测模式忽略
        window: int = 50
    ) -> PerformanceMetrics:
        """
        计算绩效指标（与 PerformanceService 接口兼容）
        
        Args:
            bot_id: 忽略（回测模式只有一个 bot）
            window: 计算窗口
            
        Returns:
            PerformanceMetrics: 绩效指标
        """
        if not self.trades:
            logger.info("No trades to calculate metrics")
            return PerformanceMetrics()
        
        recent = self.trades[-window:]
        
        returns_pct = [t.pnl_percent for t in recent]
        returns_usd = [t.pnl_usd for t in recent]
        
        if not returns_pct:
            return PerformanceMetrics(total_trades=len(recent))
        
        returns_array = np.array(returns_pct)
        
        # 基础统计
        total_trades = len(returns_pct)
        winning_trades = sum(1 for r in returns_pct if r > 0)
        losing_trades = sum(1 for r in returns_pct if r < 0)
        
        # 胜率
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        # 平均收益
        avg_return_pct = float(np.mean(returns_array))
        total_return_usd = sum(returns_usd)
        
        # 平均盈利/亏损
        wins = [r for r in returns_pct if r > 0]
        losses = [r for r in returns_pct if r < 0]
        avg_win_pct = float(np.mean(wins)) if wins else 0
        avg_loss_pct = float(np.mean(losses)) if losses else 0
        
        # 盈亏比 (Profit Factor)
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        profit_factor = (total_wins / total_losses) if total_losses > 0 else 0
        
        # 夏普比率
        sharpe_ratio = self._calculate_sharpe(returns_array)
        
        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(returns_pct)
        
        metrics = PerformanceMetrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_return_pct=avg_return_pct,
            total_return_usd=total_return_usd,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            avg_win_pct=avg_win_pct,
            avg_loss_pct=avg_loss_pct,
            profit_factor=profit_factor,
        )
        
        logger.info(
            f"📊 Backtest Performance: "
            f"trades={total_trades}, win_rate={win_rate:.1f}%, "
            f"sharpe={sharpe_ratio:.2f}, total_pnl=${total_return_usd:.2f}"
        )
        
        return metrics
    
    def _calculate_sharpe(
        self, 
        returns: np.ndarray, 
        risk_free_rate: float = 0.0
    ) -> float:
        """计算夏普比率"""
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        
        if std_return == 0:
            return 0.0
        
        return float((mean_return - risk_free_rate) / std_return)
    
    def _calculate_max_drawdown(self, returns_pct: List[float]) -> float:
        """计算最大回撤"""
        if not returns_pct:
            return 0.0
        
        cumulative = [0.0]
        for r in returns_pct:
            cumulative.append(cumulative[-1] + r)
        
        peak = cumulative[0]
        max_dd = 0.0
        
        for value in cumulative:
            if value > peak:
                peak = value
            drawdown = peak - value
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def get_recent_trades_summary(
        self, 
        bot_id: int = 0,  # 兼容接口
        limit: int = 10
    ) -> str:
        """获取最近交易摘要（与 PerformanceService 接口兼容）"""
        if not self.trades:
            return "No recent trades.\n"
        
        recent = self.trades[-limit:]
        
        text = f"Recent {len(recent)} Trades:\n"
        for i, trade in enumerate(recent, 1):
            emoji = "✅" if trade.pnl_percent > 0 else "❌" if trade.pnl_percent < 0 else "➖"
            text += f"  {i}. {trade.symbol} {trade.side}: {emoji} {trade.pnl_percent:+.2f}%\n"
        
        return text
    
    def clear(self):
        """清空交易记录"""
        self.trades.clear()
        logger.info("🧹 Trade history cleared")

