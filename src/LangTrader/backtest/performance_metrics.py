"""
性能指标计算器
"""
import pandas as pd
import numpy as np
from typing import List, Dict
from src.LangTrader.backtest.mock_position import MockPosition

class PerformanceAnalyzer:
    """性能分析器"""
    
    def __init__(
        self,
        closed_positions: List[MockPosition],
        equity_curve: List[Dict],
        initial_balance: float,
        final_balance: float
    ):
        self.closed_positions = closed_positions
        self.equity_curve = equity_curve
        self.initial_balance = initial_balance
        self.final_balance = final_balance
    
    def calculate_all_metrics(self) -> Dict:
        """计算所有性能指标"""
        if not self.closed_positions:
            return self._empty_metrics()
        
        trades_df = pd.DataFrame([pos.to_dict() for pos in self.closed_positions])
        
        # 基础指标
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['realized_pnl'] > 0])
        losing_trades = len(trades_df[trades_df['realized_pnl'] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # 盈亏统计
        total_pnl = trades_df['realized_pnl'].sum()
        total_return = (self.final_balance - self.initial_balance) / self.initial_balance
        
        avg_win = trades_df[trades_df['realized_pnl'] > 0]['realized_pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['realized_pnl'] < 0]['realized_pnl'].mean() if losing_trades > 0 else 0
        
        largest_win = trades_df['realized_pnl'].max()
        largest_loss = trades_df['realized_pnl'].min()
        
        # 盈亏比
        total_wins = trades_df[trades_df['realized_pnl'] > 0]['realized_pnl'].sum()
        total_losses = abs(trades_df[trades_df['realized_pnl'] < 0]['realized_pnl'].sum())
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        # 最大回撤
        max_drawdown = self._calculate_max_drawdown()
        
        # 夏普率
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        # 按币种统计
        by_symbol = self._calculate_by_symbol(trades_df)
        
        # 按策略统计（如果有）
        by_strategy = self._calculate_by_strategy(trades_df)
        
        return {
            'initial_balance': float(self.initial_balance),
            'final_balance': float(self.final_balance),
            'total_pnl': float(total_pnl),
            'total_return': float(total_return),
            
            'total_trades': int(total_trades),
            'winning_trades': int(winning_trades),
            'losing_trades': int(losing_trades),
            'win_rate': float(win_rate),
            
            'avg_win': float(avg_win),
            'avg_loss': float(avg_loss),
            'largest_win': float(largest_win),
            'largest_loss': float(largest_loss),
            'profit_factor': float(profit_factor),
            
            'max_drawdown': float(max_drawdown),
            'sharpe_ratio': float(sharpe_ratio),
            
            'by_symbol': by_symbol,
            'by_strategy': by_strategy
        }
    
    def _calculate_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self.equity_curve:
            return 0.0
        
        equity_series = pd.Series([point['equity'] for point in self.equity_curve])
        running_max = equity_series.cummax()
        drawdown = (equity_series - running_max) / running_max
        return float(drawdown.min())
    
    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """计算夏普率（年化）"""
        if len(self.equity_curve) < 2:
            return 0.0
        
        equity_series = pd.Series([point['equity'] for point in self.equity_curve])
        returns = equity_series.pct_change().dropna()
        
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        
        # 假设4小时K线，一年约2190根（365*24/4）
        periods_per_year = 2190
        
        avg_return = returns.mean()
        std_return = returns.std()
        
        sharpe = (avg_return - risk_free_rate) / std_return * np.sqrt(periods_per_year)
        
        return float(sharpe)
    
    def _calculate_by_symbol(self, trades_df: pd.DataFrame) -> Dict:
        """按币种统计"""
        by_symbol = {}
        
        for symbol in trades_df['symbol'].unique():
            symbol_trades = trades_df[trades_df['symbol'] == symbol]
            
            by_symbol[symbol] = {
                'total_trades': len(symbol_trades),
                'win_rate': float((symbol_trades['realized_pnl'] > 0).mean()),
                'total_pnl': float(symbol_trades['realized_pnl'].sum())
            }
        
        return by_symbol
    
    def _calculate_by_strategy(self, trades_df: pd.DataFrame) -> Dict:
        """按策略统计（如果记录了策略名）"""
        if 'strategy_name' not in trades_df.columns:
            return {}
        
        by_strategy = {}
        
        for strategy in trades_df['strategy_name'].dropna().unique():
            strategy_trades = trades_df[trades_df['strategy_name'] == strategy]
            
            by_strategy[strategy] = {
                'total_trades': len(strategy_trades),
                'win_rate': float((strategy_trades['realized_pnl'] > 0).mean()),
                'total_pnl': float(strategy_trades['realized_pnl'].sum())
            }
        
        return by_strategy
    
    def _empty_metrics(self) -> Dict:
        """无交易时的空指标"""
        return {
            'initial_balance': float(self.initial_balance),
            'final_balance': float(self.final_balance),
            'total_pnl': 0.0,
            'total_return': 0.0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'by_symbol': {},
            'by_strategy': {}
        }