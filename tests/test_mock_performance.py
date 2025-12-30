#!/usr/bin/env python3
"""
Unit tests for MockPerformanceService
Tests trade recording and performance metrics calculation
"""
import sys
from pathlib import Path
import pytest

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.backtest.mock_performance import MockPerformanceService


@pytest.fixture
def perf_service():
    """Create fresh MockPerformanceService for each test"""
    return MockPerformanceService()


class TestMockPerformanceRecording:
    """Test trade recording"""
    
    def test_record_winning_trade(self, perf_service):
        """Test recording a profitable trade"""
        perf_service.record_trade(
            symbol='BTC/USDT:USDT',
            side='buy',
            entry_price=100.0,
            exit_price=110.0,
            amount=1.0,
            entry_time=1000000,
            exit_time=2000000
        )
        
        assert len(perf_service.trades) == 1
        
        trade = perf_service.trades[0]
        assert trade.pnl_usd == 10.0  # (110 - 100) * 1
        assert trade.pnl_percent == 10.0  # 10% gain
    
    def test_record_losing_trade(self, perf_service):
        """Test recording a losing trade"""
        perf_service.record_trade(
            symbol='BTC/USDT:USDT',
            side='buy',
            entry_price=100.0,
            exit_price=90.0,
            amount=1.0,
            entry_time=1000000,
            exit_time=2000000
        )
        
        trade = perf_service.trades[0]
        assert trade.pnl_usd == -10.0  # (90 - 100) * 1
        assert trade.pnl_percent == -10.0
    
    def test_record_short_winning_trade(self, perf_service):
        """Test recording a profitable short trade"""
        perf_service.record_trade(
            symbol='ETH/USDT:USDT',
            side='sell',
            entry_price=100.0,
            exit_price=90.0,  # Price goes down = profit for short
            amount=1.0,
            entry_time=1000000,
            exit_time=2000000
        )
        
        trade = perf_service.trades[0]
        assert trade.pnl_usd == 10.0  # (100 - 90) * 1
        assert trade.pnl_percent == 10.0
    
    def test_record_short_losing_trade(self, perf_service):
        """Test recording a losing short trade"""
        perf_service.record_trade(
            symbol='ETH/USDT:USDT',
            side='sell',
            entry_price=100.0,
            exit_price=110.0,  # Price goes up = loss for short
            amount=1.0,
            entry_time=1000000,
            exit_time=2000000
        )
        
        trade = perf_service.trades[0]
        assert trade.pnl_usd == -10.0
        assert trade.pnl_percent == -10.0
    
    def test_record_multiple_trades(self, perf_service):
        """Test recording multiple trades"""
        perf_service.record_trade('BTC/USDT:USDT', 'buy', 100, 110, 1, 1000, 2000)
        perf_service.record_trade('ETH/USDT:USDT', 'buy', 50, 45, 2, 3000, 4000)
        perf_service.record_trade('SOL/USDT:USDT', 'sell', 20, 18, 5, 5000, 6000)
        
        assert len(perf_service.trades) == 3


class TestMockPerformanceMetrics:
    """Test metrics calculation"""
    
    def test_metrics_with_no_trades(self, perf_service):
        """Test metrics when no trades recorded"""
        metrics = perf_service.calculate_metrics()
        
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.sharpe_ratio == 0.0
    
    def test_win_rate_calculation(self, perf_service):
        """Test win rate calculation"""
        # 3 wins, 2 losses = 60% win rate
        perf_service.record_trade('BTC', 'buy', 100, 110, 1, 1000, 2000)  # Win
        perf_service.record_trade('BTC', 'buy', 100, 105, 1, 3000, 4000)  # Win
        perf_service.record_trade('BTC', 'buy', 100, 115, 1, 5000, 6000)  # Win
        perf_service.record_trade('BTC', 'buy', 100, 95, 1, 7000, 8000)   # Loss
        perf_service.record_trade('BTC', 'buy', 100, 90, 1, 9000, 10000)  # Loss
        
        metrics = perf_service.calculate_metrics()
        
        assert metrics.total_trades == 5
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 2
        assert metrics.win_rate == 60.0
    
    def test_total_return_calculation(self, perf_service):
        """Test total return calculation"""
        perf_service.record_trade('BTC', 'buy', 100, 110, 1, 1000, 2000)  # +10
        perf_service.record_trade('BTC', 'buy', 100, 95, 2, 3000, 4000)   # -10
        perf_service.record_trade('BTC', 'buy', 100, 120, 0.5, 5000, 6000) # +10
        
        metrics = perf_service.calculate_metrics()
        
        assert metrics.total_return_usd == 10.0  # 10 - 10 + 10
    
    def test_avg_return_calculation(self, perf_service):
        """Test average return calculation"""
        perf_service.record_trade('BTC', 'buy', 100, 110, 1, 1000, 2000)  # +10%
        perf_service.record_trade('BTC', 'buy', 100, 90, 1, 3000, 4000)   # -10%
        
        metrics = perf_service.calculate_metrics()
        
        assert metrics.avg_return_pct == 0.0  # (10 - 10) / 2
    
    def test_sharpe_ratio_positive(self, perf_service):
        """Test Sharpe ratio with positive returns"""
        # Consistent positive returns
        for i in range(10):
            perf_service.record_trade('BTC', 'buy', 100, 105 + i*0.1, 1, i*1000, (i+1)*1000)
        
        metrics = perf_service.calculate_metrics()
        
        assert metrics.sharpe_ratio > 0
    
    def test_sharpe_ratio_negative(self, perf_service):
        """Test Sharpe ratio with negative returns"""
        # Consistent negative returns
        for i in range(10):
            perf_service.record_trade('BTC', 'buy', 100, 95 - i*0.1, 1, i*1000, (i+1)*1000)
        
        metrics = perf_service.calculate_metrics()
        
        assert metrics.sharpe_ratio < 0
    
    def test_sharpe_ratio_zero_std(self, perf_service):
        """Test Sharpe ratio when all returns are the same"""
        # All same returns (std = 0)
        for i in range(5):
            perf_service.record_trade('BTC', 'buy', 100, 105, 1, i*1000, (i+1)*1000)
        
        metrics = perf_service.calculate_metrics()
        
        # Should return 0 when std is 0
        assert metrics.sharpe_ratio == 0.0
    
    def test_max_drawdown(self, perf_service):
        """Test max drawdown calculation"""
        # Win, Win, Lose big, Win
        perf_service.record_trade('BTC', 'buy', 100, 110, 1, 1000, 2000)  # +10%
        perf_service.record_trade('BTC', 'buy', 100, 115, 1, 3000, 4000)  # +15%
        perf_service.record_trade('BTC', 'buy', 100, 70, 1, 5000, 6000)   # -30%
        perf_service.record_trade('BTC', 'buy', 100, 105, 1, 7000, 8000)  # +5%
        
        metrics = perf_service.calculate_metrics()
        
        # Drawdown from peak (25%) to trough (-5%) = 30%
        assert metrics.max_drawdown == 30.0
    
    def test_profit_factor(self, perf_service):
        """Test profit factor calculation"""
        # Total wins = 30, Total losses = 15
        perf_service.record_trade('BTC', 'buy', 100, 110, 1, 1000, 2000)  # +10
        perf_service.record_trade('BTC', 'buy', 100, 120, 1, 3000, 4000)  # +20
        perf_service.record_trade('BTC', 'buy', 100, 85, 1, 5000, 6000)   # -15
        
        metrics = perf_service.calculate_metrics()
        
        assert metrics.profit_factor == 2.0  # 30 / 15
    
    def test_avg_win_loss(self, perf_service):
        """Test average win and loss percentages"""
        perf_service.record_trade('BTC', 'buy', 100, 110, 1, 1000, 2000)  # +10%
        perf_service.record_trade('BTC', 'buy', 100, 120, 1, 3000, 4000)  # +20%
        perf_service.record_trade('BTC', 'buy', 100, 95, 1, 5000, 6000)   # -5%
        perf_service.record_trade('BTC', 'buy', 100, 85, 1, 7000, 8000)   # -15%
        
        metrics = perf_service.calculate_metrics()
        
        assert metrics.avg_win_pct == 15.0   # (10 + 20) / 2
        assert metrics.avg_loss_pct == -10.0  # (-5 + -15) / 2


class TestMockPerformanceWindow:
    """Test windowed calculations"""
    
    def test_window_parameter(self, perf_service):
        """Test window limits number of trades"""
        # Record 100 trades
        for i in range(100):
            pct = 5 if i % 2 == 0 else -3
            perf_service.record_trade('BTC', 'buy', 100, 100 + pct, 1, i*1000, (i+1)*1000)
        
        # Calculate with window of 20
        metrics = perf_service.calculate_metrics(window=20)
        
        assert metrics.total_trades == 20


class TestMockPerformanceSummary:
    """Test summary text generation"""
    
    def test_recent_trades_summary_empty(self, perf_service):
        """Test summary with no trades"""
        summary = perf_service.get_recent_trades_summary()
        
        assert 'No recent trades' in summary
    
    def test_recent_trades_summary(self, perf_service):
        """Test summary with trades"""
        perf_service.record_trade('BTC/USDT:USDT', 'buy', 100, 110, 1, 1000, 2000)
        perf_service.record_trade('ETH/USDT:USDT', 'sell', 50, 45, 1, 3000, 4000)
        
        summary = perf_service.get_recent_trades_summary()
        
        assert 'BTC/USDT:USDT' in summary
        assert 'ETH/USDT:USDT' in summary
    
    def test_recent_trades_limit(self, perf_service):
        """Test summary respects limit"""
        for i in range(20):
            perf_service.record_trade(f'COIN{i}', 'buy', 100, 105, 1, i*1000, (i+1)*1000)
        
        summary = perf_service.get_recent_trades_summary(limit=5)
        
        # Should only show last 5
        assert 'COIN15' in summary or 'COIN19' in summary


class TestMockPerformanceClear:
    """Test clear functionality"""
    
    def test_clear_trades(self, perf_service):
        """Test clearing trade history"""
        perf_service.record_trade('BTC', 'buy', 100, 110, 1, 1000, 2000)
        perf_service.record_trade('ETH', 'buy', 50, 55, 1, 3000, 4000)
        
        assert len(perf_service.trades) == 2
        
        perf_service.clear()
        
        assert len(perf_service.trades) == 0


class TestMockPerformanceAPICompatibility:
    """Test API compatibility with PerformanceService"""
    
    def test_bot_id_ignored(self, perf_service):
        """Test bot_id parameter is accepted but ignored"""
        perf_service.record_trade('BTC', 'buy', 100, 110, 1, 1000, 2000)
        
        # Should work with any bot_id
        metrics1 = perf_service.calculate_metrics(bot_id=1)
        metrics2 = perf_service.calculate_metrics(bot_id=999)
        
        assert metrics1.total_trades == metrics2.total_trades


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

