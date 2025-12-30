#!/usr/bin/env python3
"""
Unit tests for State models (Pydantic validation)
Tests Account, Position, AIDecision, ExecutionResult, State
"""
import sys
from pathlib import Path
from datetime import datetime
import pytest

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.graph.state import (
    Account, Position, AIDecision, ExecutionResult,
    OpenPositionResult, OrderResult, RunRecord, State,
    PerformanceMetrics
)


class TestAccount:
    """Test Account model"""
    
    def test_create_account(self):
        """Test creating a valid account"""
        account = Account(
            timestamp=datetime.now(),
            free={'USDT': 10000.0, 'BTC': 0.5},
            used={'USDT': 500.0},
            total={'USDT': 10500.0, 'BTC': 0.5},
            debt={'USDT': 0.0}
        )
        
        assert account.free['USDT'] == 10000.0
        assert account.total['BTC'] == 0.5
        assert account.debt['USDT'] == 0.0
    
    def test_account_empty_balances(self):
        """Test account with empty balances"""
        account = Account(timestamp=datetime.now())
        
        assert account.free == {}
        assert account.used == {}
        assert account.total == {}
    
    def test_account_serialization(self):
        """Test account serialization to dict"""
        account = Account(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            free={'USDT': 1000.0}
        )
        
        data = account.model_dump()
        assert 'timestamp' in data
        assert data['free']['USDT'] == 1000.0


class TestPosition:
    """Test Position model"""
    
    def test_create_long_position(self):
        """Test creating a long position"""
        position = Position(
            id='pos_001',
            symbol='BTC/USDT:USDT',
            side='buy',
            type='market',
            status='open',
            datetime=datetime.now(),
            price=50000.0,
            average=50000.0,
            amount=0.1
        )
        
        assert position.side == 'buy'
        assert position.amount == 0.1
        assert position.status == 'open'
    
    def test_create_short_position(self):
        """Test creating a short position"""
        position = Position(
            id='pos_002',
            symbol='ETH/USDT:USDT',
            side='sell',
            type='limit',
            status='open',
            datetime=datetime.now(),
            price=3000.0,
            average=3000.0,
            amount=1.0
        )
        
        assert position.side == 'sell'
        assert position.type == 'limit'
    
    def test_position_with_sl_tp(self):
        """Test position with stop loss and take profit"""
        position = Position(
            id='pos_003',
            symbol='BTC/USDT:USDT',
            side='buy',
            type='market',
            status='open',
            datetime=datetime.now(),
            price=50000.0,
            average=50000.0,
            amount=0.1,
            stop_loss_price=48000.0,
            take_profit_price=55000.0
        )
        
        assert position.stop_loss_price == 48000.0
        assert position.take_profit_price == 55000.0
    
    def test_position_status_values(self):
        """Test valid status values"""
        for status in ['open', 'closed', 'canceled', 'expired', 'rejected']:
            position = Position(
                id='pos_test',
                symbol='BTC/USDT:USDT',
                side='buy',
                type='market',
                status=status,
                datetime=datetime.now(),
                price=100.0,
                average=100.0,
                amount=1.0
            )
            assert position.status == status


class TestAIDecision:
    """Test AIDecision model"""
    
    def test_open_long_decision(self):
        """Test open long decision"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='open_long',
            leverage=3,
            position_size_usd=1000.0,
            stop_loss_price=48000.0,
            take_profit_price=55000.0,
            confidence=0.85,
            risk_usd=50.0,
            reasons=['Bullish trend', 'Volume spike']
        )
        
        assert decision.action == 'open_long'
        assert decision.leverage == 3
        assert decision.confidence == 0.85
        assert len(decision.reasons) == 2
    
    def test_wait_decision(self):
        """Test wait decision (no trade)"""
        decision = AIDecision(
            symbol='ETH/USDT:USDT',
            action='wait',
            confidence=0.3,
            reasons=['Market uncertain']
        )
        
        assert decision.action == 'wait'
        assert decision.position_size_usd == 0.0
    
    def test_close_decision(self):
        """Test close position decision"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='close_long',
            confidence=0.7,
            reasons=['Take profit reached']
        )
        
        assert decision.action == 'close_long'
    
    def test_valid_actions(self):
        """Test all valid action types"""
        valid_actions = ['open_long', 'open_short', 'close_long', 'close_short', 'hold', 'wait']
        
        for action in valid_actions:
            decision = AIDecision(
                symbol='BTC/USDT:USDT',
                action=action,
                confidence=0.5
            )
            assert decision.action == action
    
    def test_default_values(self):
        """Test default values are set correctly"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='wait'
        )
        
        assert decision.leverage == 1
        assert decision.position_size_usd == 0.0
        assert decision.confidence == 0.0
        assert decision.risk_approved == False
        assert decision.reasons == []


class TestExecutionResult:
    """Test ExecutionResult model"""
    
    def test_successful_execution(self):
        """Test successful execution result"""
        result = ExecutionResult(
            symbol='BTC/USDT:USDT',
            action='open_long',
            status='success',
            message='Order filled',
            order_id='ord_12345',
            executed_price=50000.0,
            executed_amount=0.1,
            fee_paid=2.5
        )
        
        assert result.status == 'success'
        assert result.executed_price == 50000.0
        assert result.fee_paid == 2.5
    
    def test_skipped_execution(self):
        """Test skipped execution (wait action)"""
        result = ExecutionResult(
            symbol='ETH/USDT:USDT',
            action='wait',
            status='skipped',
            message='No action required'
        )
        
        assert result.status == 'skipped'
        assert result.order_id is None
    
    def test_failed_execution(self):
        """Test failed execution"""
        result = ExecutionResult(
            symbol='BTC/USDT:USDT',
            action='open_long',
            status='failed',
            message='Insufficient balance'
        )
        
        assert result.status == 'failed'
    
    def test_valid_statuses(self):
        """Test all valid status values"""
        for status in ['skipped', 'pending', 'success', 'failed']:
            result = ExecutionResult(
                symbol='BTC/USDT:USDT',
                action='wait',
                status=status
            )
            assert result.status == status


class TestOrderResult:
    """Test OrderResult model"""
    
    def test_successful_order(self):
        """Test successful order result"""
        result = OrderResult(
            success=True,
            order_id='ord_123',
            symbol='BTC/USDT:USDT',
            status='closed',
            filled=0.1,
            remaining=0.0,
            average=50000.0,
            fee=2.5
        )
        
        assert result.success == True
        assert result.filled == 0.1
        assert result.average == 50000.0
    
    def test_failed_order(self):
        """Test failed order result"""
        result = OrderResult(
            success=False,
            error='Insufficient margin'
        )
        
        assert result.success == False
        assert result.error == 'Insufficient margin'
        assert result.order_id is None


class TestPerformanceMetrics:
    """Test PerformanceMetrics model"""
    
    def test_create_metrics(self):
        """Test creating performance metrics"""
        metrics = PerformanceMetrics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=60.0,
            avg_return_pct=1.5,
            total_return_usd=1500.0,
            sharpe_ratio=1.2,
            max_drawdown=8.5
        )
        
        assert metrics.total_trades == 100
        assert metrics.win_rate == 60.0
        assert metrics.sharpe_ratio == 1.2
    
    def test_empty_metrics(self):
        """Test empty metrics (no trades)"""
        metrics = PerformanceMetrics()
        
        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
    
    def test_to_prompt_text_no_trades(self):
        """Test prompt text with no trades"""
        metrics = PerformanceMetrics()
        text = metrics.to_prompt_text()
        
        assert 'No historical trades' in text
    
    def test_to_prompt_text_with_trades(self):
        """Test prompt text with trades"""
        metrics = PerformanceMetrics(
            total_trades=50,
            win_rate=55.0,
            sharpe_ratio=0.8,
            avg_return_pct=0.5,
            total_return_usd=500.0,
            max_drawdown=5.0
        )
        
        text = metrics.to_prompt_text()
        assert 'Total Trades: 50' in text
        assert 'Win Rate: 55.0%' in text


class TestState:
    """Test State model"""
    
    def test_create_minimal_state(self):
        """Test creating minimal state"""
        state = State(bot_id=1)
        
        assert state.bot_id == 1
        assert state.symbols == []
        assert state.market_data == {}
        assert state.runs == {}
    
    def test_create_full_state(self, sample_account, sample_indicators):
        """Test creating full state with all fields"""
        state = State(
            bot_id=1,
            prompt_name='custom.txt',
            initial_balance=10000.0,
            symbols=['BTC/USDT:USDT', 'ETH/USDT:USDT'],
            account=sample_account,
            positions=[],
            market_data={
                'BTC/USDT:USDT': {'indicators': sample_indicators}
            }
        )
        
        assert state.prompt_name == 'custom.txt'
        assert len(state.symbols) == 2
        assert 'BTC/USDT:USDT' in state.market_data
    
    def test_state_with_runs(self):
        """Test state with run records"""
        run_record = RunRecord(
            run_id='run_001',
            cycle_id='cycle_001',
            symbol='BTC/USDT:USDT',
            cycle_time=datetime.now()
        )
        
        state = State(
            bot_id=1,
            runs={'BTC/USDT:USDT': run_record}
        )
        
        assert 'BTC/USDT:USDT' in state.runs
        assert state.runs['BTC/USDT:USDT'].run_id == 'run_001'


class TestRunRecord:
    """Test RunRecord model"""
    
    def test_create_run_record(self):
        """Test creating run record"""
        record = RunRecord(
            run_id='run_001',
            cycle_id='cycle_001',
            symbol='BTC/USDT:USDT',
            cycle_time=datetime.now()
        )
        
        assert record.run_id == 'run_001'
        assert record.decision is None
        assert record.execution is None
    
    def test_run_record_with_decision(self):
        """Test run record with decision"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='open_long',
            confidence=0.8
        )
        
        record = RunRecord(
            run_id='run_002',
            cycle_id='cycle_002',
            symbol='BTC/USDT:USDT',
            cycle_time=datetime.now(),
            decision=decision
        )
        
        assert record.decision.action == 'open_long'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

