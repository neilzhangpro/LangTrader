# packages/langtrader_core/backtest/__init__.py
"""
回测模块
提供基于历史数据的策略测试能力
"""
from langtrader_core.backtest.mock_trader import MockTrader, BacktestDataSource, ExchangeBacktestDataSource
from langtrader_core.backtest.mock_performance import MockPerformanceService
from langtrader_core.backtest.engine import BacktestEngine

__all__ = [
    'MockTrader',
    'BacktestDataSource',
    'ExchangeBacktestDataSource',
    'MockPerformanceService',
    'BacktestEngine',
]

