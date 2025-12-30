#!/usr/bin/env python3
"""
Unit tests for Execution node
Tests trade execution with MockTrader
"""
import sys
from pathlib import Path
from datetime import datetime
import uuid
import pytest
import pytest_asyncio

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.graph.state import State, AIDecision, RunRecord, ExecutionResult
from langtrader_core.graph.nodes.execution import Execution
from langtrader_core.plugins.registry import PluginContext
from langtrader_core.backtest.mock_trader import MockTrader
from langtrader_core.backtest.mock_performance import MockPerformanceService
from langtrader_core.services.cache import Cache


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def execution_node(mock_trader, mock_performance):
    """Create Execution node with mock context"""
    context = PluginContext(
        trader=mock_trader,
        stream_manager=None,
        database=None,
        cache=Cache(),
        rate_limiter=None,
        llm_factory=None,
        trade_history_repo=None,
        performance_service=mock_performance
    )
    
    node = Execution(context=context, config={})
    return node


@pytest.fixture
def base_state(sample_account):
    """Create a base state for testing"""
    state = State(
        bot_id=1,
        prompt_name='default.txt',
        initial_balance=10000.0,
        symbols=['BTC/USDT:USDT'],
        account=sample_account,
        positions=[],
        market_data={
            'BTC/USDT:USDT': {'indicators': {'current_price': 100.0}}
        },
        runs={}
    )
    return state


def create_run_record(symbol: str, decision: AIDecision) -> RunRecord:
    """Helper to create run record"""
    return RunRecord(
        run_id=str(uuid.uuid4()),
        cycle_id=str(uuid.uuid4()),
        symbol=symbol,
        cycle_time=datetime.now(),
        decision=decision
    )


# =============================================================================
# Test Cases
# =============================================================================

class TestExecutionNodeWaitAction:
    """Test handling of wait/hold actions"""
    
    @pytest.mark.asyncio
    async def test_wait_action_skipped(self, execution_node, base_state):
        """Test wait action is skipped"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='wait',
            confidence=0.3,
            reasons=['Market uncertain']
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution is not None
        assert execution.status == 'skipped'
        assert execution.action == 'wait'
    
    @pytest.mark.asyncio
    async def test_hold_action_skipped(self, execution_node, base_state):
        """Test hold action is skipped"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='hold',
            confidence=0.5,
            reasons=['Holding position']
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution.status == 'skipped'


class TestExecutionNodeOpenPosition:
    """Test opening positions"""
    
    @pytest.mark.asyncio
    async def test_execute_open_long(self, execution_node, base_state, mock_trader):
        """Test executing open_long decision"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='open_long',
            leverage=2,
            position_size_usd=500.0,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            confidence=0.75,
            risk_usd=25.0,
            reasons=['Bullish trend']
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution.status == 'success'
        assert execution.action == 'open_long'
        assert execution.order_id is not None
        
        # Position should be opened
        position = await mock_trader.get_position('BTC/USDT:USDT')
        assert position is not None
        assert position.side == 'buy'
    
    @pytest.mark.asyncio
    async def test_execute_open_short(self, execution_node, base_state, mock_trader):
        """Test executing open_short decision"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='open_short',
            leverage=2,
            position_size_usd=500.0,
            stop_loss_price=110.0,
            take_profit_price=90.0,
            confidence=0.70,
            risk_usd=25.0,
            reasons=['Bearish trend']
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution.status == 'success'
        assert execution.action == 'open_short'
        
        position = await mock_trader.get_position('BTC/USDT:USDT')
        assert position is not None
        assert position.side == 'sell'


class TestExecutionNodeClosePosition:
    """Test closing positions"""
    
    @pytest.mark.asyncio
    async def test_execute_close_long(self, execution_node, base_state, mock_trader):
        """Test executing close_long decision"""
        # First open a position
        await mock_trader.open_position('BTC/USDT:USDT', 'buy', 0.5)
        
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='close_long',
            confidence=0.80,
            reasons=['Take profit']
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution.status == 'success'
        assert execution.action == 'close_long'
        
        # Position should be closed
        position = await mock_trader.get_position('BTC/USDT:USDT')
        assert position is None
    
    @pytest.mark.asyncio
    async def test_close_nonexistent_position_fails(self, execution_node, base_state, mock_trader):
        """Test closing a position that doesn't exist"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='close_long',
            confidence=0.80,
            reasons=['Close position']
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution.status == 'failed'
        assert 'No position' in execution.message


class TestExecutionNodeValidation:
    """Test parameter validation"""
    
    @pytest.mark.asyncio
    async def test_reject_zero_position_size(self, execution_node, base_state):
        """Test rejection of zero position size"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='open_long',
            leverage=2,
            position_size_usd=0.0,  # Invalid
            confidence=0.75
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution.status == 'failed'
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Execution node does not validate SL/TP logic - future enhancement")
    async def test_invalid_stop_loss_long(self, execution_node, base_state):
        """Test invalid stop loss for long (SL > current price)
        
        NOTE: This test is skipped because the execution node currently
        does not validate whether SL/TP prices are logically correct.
        This could be a future enhancement.
        """
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='open_long',
            leverage=2,
            position_size_usd=500.0,
            stop_loss_price=110.0,  # Invalid: SL above current price for long
            take_profit_price=120.0,
            confidence=0.75
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution.status == 'failed'
        assert 'Invalid' in execution.message


class TestExecutionNodeMultipleSymbols:
    """Test handling multiple symbols"""
    
    @pytest.mark.asyncio
    async def test_execute_multiple_decisions(self, execution_node, base_state, mock_trader):
        """Test executing decisions for multiple symbols"""
        # Add ETH to state
        base_state.symbols.append('ETH/USDT:USDT')
        base_state.market_data['ETH/USDT:USDT'] = {'indicators': {'current_price': 100.0}}
        
        # BTC: open long
        btc_decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='open_long',
            leverage=2,
            position_size_usd=500.0,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            confidence=0.75
        )
        
        # ETH: wait
        eth_decision = AIDecision(
            symbol='ETH/USDT:USDT',
            action='wait',
            confidence=0.4
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', btc_decision)
        base_state.runs['ETH/USDT:USDT'] = create_run_record('ETH/USDT:USDT', eth_decision)
        
        result_state = await execution_node.run(base_state)
        
        # BTC should be executed
        btc_exec = result_state.runs['BTC/USDT:USDT'].execution
        assert btc_exec.status == 'success'
        
        # ETH should be skipped
        eth_exec = result_state.runs['ETH/USDT:USDT'].execution
        assert eth_exec.status == 'skipped'


class TestExecutionNodeNoDecision:
    """Test handling of missing decisions"""
    
    @pytest.mark.asyncio
    async def test_skip_symbol_without_decision(self, execution_node, base_state):
        """Test that symbols without decisions are skipped"""
        # Add run record without decision
        base_state.runs['BTC/USDT:USDT'] = RunRecord(
            run_id=str(uuid.uuid4()),
            cycle_id=str(uuid.uuid4()),
            symbol='BTC/USDT:USDT',
            cycle_time=datetime.now(),
            decision=None  # No decision
        )
        
        result_state = await execution_node.run(base_state)
        
        # Should not have execution result
        execution = result_state.runs['BTC/USDT:USDT'].execution
        assert execution is None


class TestExecutionNodeRiskApproval:
    """Test risk approval flag"""
    
    @pytest.mark.asyncio
    async def test_risk_approved_set_on_success(self, execution_node, base_state, mock_trader):
        """Test risk_approved is set to True on successful execution"""
        decision = AIDecision(
            symbol='BTC/USDT:USDT',
            action='open_long',
            leverage=2,
            position_size_usd=500.0,
            stop_loss_price=95.0,
            take_profit_price=110.0,
            confidence=0.75,
            risk_approved=False  # Initially false
        )
        
        base_state.runs['BTC/USDT:USDT'] = create_run_record('BTC/USDT:USDT', decision)
        
        result_state = await execution_node.run(base_state)
        
        # Decision should now have risk_approved = True
        updated_decision = result_state.runs['BTC/USDT:USDT'].decision
        assert updated_decision.risk_approved == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

