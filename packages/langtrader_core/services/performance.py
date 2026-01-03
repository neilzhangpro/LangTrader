# packages/langtrader_core/services/performance.py
"""
绩效计算服务
计算夏普率、胜率、平均收益、总回报等指标
"""
from typing import List, Optional
from dataclasses import dataclass
import numpy as np
from sqlmodel import Session

from langtrader_core.data.repositories.trade_history import TradeHistoryRepository
from langtrader_core.data.models.trade_history import TradeHistory
from langtrader_core.utils import get_logger

logger = get_logger("performance_service")


@dataclass
class PerformanceMetrics:
    """绩效指标"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_return_pct: float = 0.0
    total_return_usd: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    
    def to_prompt_text(self) -> str:
        """转换为 prompt 文本"""
        if self.total_trades == 0:
            return "No historical trades yet.\n"
        
        text = "Historical Performance:\n"
        text += "-------------------\n"
        text += f"  Total Trades: {self.total_trades}\n"
        text += f"  Win Rate: {self.win_rate:.1f}%\n"
        text += f"  Sharpe Ratio: {self.sharpe_ratio:.2f}\n"
        text += f"  Avg Return per Trade: {self.avg_return_pct:.2f}%\n"
        text += f"  Total Return: ${self.total_return_usd:.2f}\n"
        text += f"  Max Drawdown: {self.max_drawdown*100:.2f}%\n"
        
        # 根据夏普比率给出策略建议
        if self.sharpe_ratio < -0.5:
            text += "\n  ⚠️ WARNING: Sharpe < -0.5 (持续亏损)\n"
            text += "  建议: 停止交易，只观望，至少6个周期不开仓\n"
        elif self.sharpe_ratio < 0:
            text += "\n  ⚠️ CAUTION: Sharpe < 0 (轻微亏损)\n"
            text += "  建议: 只做信心度>80的交易，减少频率\n"
        elif self.sharpe_ratio > 0.7:
            text += "\n  ✅ EXCELLENT: Sharpe > 0.7 (优异表现)\n"
            text += "  建议: 可适度扩大仓位\n"
        
        text += "-------------------\n"
        return text


class PerformanceService:
    """
    绩效计算服务
    从 trade_history 表计算各类绩效指标
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.repo = TradeHistoryRepository(session)
    
    def calculate_metrics(
        self, 
        bot_id: int, 
        window: int = 50
    ) -> PerformanceMetrics:
        """
        计算绩效指标
        
        Args:
            bot_id: 机器人ID
            window: 计算窗口（最近 N 笔交易）
            
        Returns:
            PerformanceMetrics: 绩效指标
        """
        # 获取已平仓交易
        trades = self.repo.get_closed_trades(bot_id, limit=window)
        
        if not trades:
            logger.info(f"No closed trades for bot {bot_id}")
            return PerformanceMetrics()
        
        # 提取收益率数组
        returns_pct = []
        returns_usd = []
        
        for trade in trades:
            if trade.pnl_percent is not None:
                returns_pct.append(float(trade.pnl_percent))
            if trade.pnl_usd is not None:
                returns_usd.append(float(trade.pnl_usd))
        
        if not returns_pct:
            return PerformanceMetrics(total_trades=len(trades))
        
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
        
        # 夏普比率 (假设无风险利率为 0)
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
            f"📊 Performance for bot {bot_id}: "
            f"trades={total_trades}, win_rate={win_rate:.1f}%, "
            f"sharpe={sharpe_ratio:.2f}, total_pnl=${total_return_usd:.2f}"
        )
        
        return metrics
    
    def _calculate_sharpe(
        self, 
        returns: np.ndarray, 
        risk_free_rate: float = 0.0,
        annualize: bool = False
    ) -> float:
        """
        计算夏普比率
        
        Sharpe = (平均收益 - 无风险利率) / 收益标准差
        
        Args:
            returns: 收益率数组 (%)
            risk_free_rate: 无风险利率
            annualize: 是否年化（对于短期交易，通常不年化）
        """
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)  # 样本标准差
        
        if std_return == 0:
            return 0.0
        
        sharpe = (mean_return - risk_free_rate) / std_return
        
        # 如果需要年化（假设每天 8 笔交易，一年 252 个交易日）
        if annualize:
            trades_per_year = 252 * 8
            sharpe = sharpe * np.sqrt(trades_per_year)
        
        return float(sharpe)
    
    def _calculate_max_drawdown(self, returns_pct: List[float]) -> float:
        """
        计算最大回撤
        
        Args:
            returns_pct: 收益率序列 (%)，如 [5.0, -3.0, 2.0] 表示 +5%, -3%, +2%
            
        Returns:
            最大回撤（比例），如 0.15 表示 15%
            注意：返回比例而非百分比，便于与 risk_limits.max_drawdown_pct 直接比较
        """
        if not returns_pct:
            return 0.0
        
        # 计算累计净值（从 1.0 开始，使用复利计算）
        # 例如：[+5%, -3%] -> [1.0, 1.05, 1.0185]
        equity = [1.0]
        for r in returns_pct:
            # r 是百分比（如 5.0 表示 5%），需要除以 100 转换为比例
            equity.append(equity[-1] * (1 + r / 100))
        
        # 计算最大回撤（相对于峰值的比例）
        peak = equity[0]
        max_dd = 0.0
        
        for value in equity:
            if value > peak:
                peak = value
            if peak > 0:
                # 回撤 = (峰值 - 当前值) / 峰值
                drawdown = (peak - value) / peak
                if drawdown > max_dd:
                    max_dd = drawdown
        
        return max_dd  # 返回比例，如 0.15 表示 15%
    
    def get_recent_trades_summary(
        self, 
        bot_id: int, 
        limit: int = 10
    ) -> str:
        """
        获取最近交易的摘要文本（可选添加到 prompt）
        """
        trades = self.repo.get_closed_trades(bot_id, limit=limit)
        
        if not trades:
            return "No recent trades.\n"
        
        text = f"Recent {len(trades)} Trades:\n"
        for i, trade in enumerate(trades, 1):
            pnl = float(trade.pnl_percent) if trade.pnl_percent else 0
            emoji = "✅" if pnl > 0 else "❌" if pnl < 0 else "➖"
            text += f"  {i}. {trade.symbol} {trade.side}: {emoji} {pnl:+.2f}%\n"
        
        return text

