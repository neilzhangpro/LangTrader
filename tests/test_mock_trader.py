#!/usr/bin/env python3
"""
Unit tests for MockTrader
Tests trading simulation including orders, positions, and balance management
"""
import sys
from pathlib import Path
from datetime import datetime
import pytest
import pytest_asyncio

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.backtest.mock_trader import MockTrader
from langtrader_core.backtest.mock_performance import MockPerformanceService


class TestMockTraderInitialization:
    """Test MockTrader initialization"""
    
    @pytest.mark.asyncio
    async def test_initial_balance(self, mock_trader):
        """Test initial balance is set correctly"""
        assert mock_trader.initial_balance == 10000.0
        assert mock_trader.balance == 10000.0
    
    @pytest.mark.asyncio
    async def test_initial_positions_empty(self, mock_trader):
        """Test no positions on init"""
        positions = await mock_trader.get_positions()
        assert len(positions) == 0
    
    @pytest.mark.asyncio
    async def test_markets_loaded(self, mock_trader):
        """Test markets are loaded"""
        assert mock_trader.markets is not None
        assert 'BTC/USDT:USDT' in mock_trader.markets
    
    @pytest.mark.asyncio
    async def test_exchange_attributes(self, mock_trader):
        """Test exchange compatibility attributes"""
        assert mock_trader.exchange == mock_trader  # Points to self
        assert mock_trader.has['fetchOHLCV'] == True
        assert mock_trader.has['fetchFundingRates'] == True
        assert mock_trader.has['fetchOpenInterests'] == False


class TestMockTraderOrders:
    """Test order creation and execution"""
    
    @pytest.mark.asyncio
    async def test_create_buy_order(self, mock_trader):
        """Test creating a buy order"""
        order = await mock_trader.create_order(
            symbol='BTC/USDT:USDT',
            order_type='market',
            side='buy',
            amount=1.0
        )
        
        assert order['symbol'] == 'BTC/USDT:USDT'
        assert order['side'] == 'buy'
        assert order['amount'] == 1.0
        assert order['filled'] == 1.0
        assert order['status'] == 'closed'
        assert 'fee' in order
    
    @pytest.mark.asyncio
    async def test_create_sell_order(self, mock_trader):
        """Test creating a sell order"""
        order = await mock_trader.create_order(
            symbol='ETH/USDT:USDT',
            order_type='market',
            side='sell',
            amount=2.0
        )
        
        assert order['side'] == 'sell'
        assert order['amount'] == 2.0
    
    @pytest.mark.asyncio
    async def test_order_slippage_applied(self, mock_trader):
        """Test slippage is applied to fill price"""
        # Get current price
        price_before = await mock_trader._get_current_price('BTC/USDT:USDT')
        
        # Buy order should have higher fill price (slippage)
        order = await mock_trader.create_order(
            symbol='BTC/USDT:USDT',
            order_type='market',
            side='buy',
            amount=1.0
        )
        
        expected_price = price_before * (1 + mock_trader.slippage)
        assert abs(order['average'] - expected_price) < 0.01
    
    @pytest.mark.asyncio
    async def test_order_commission_deducted(self, mock_trader):
        """Test commission is calculated"""
        order = await mock_trader.create_order(
            symbol='BTC/USDT:USDT',
            order_type='market',
            side='buy',
            amount=1.0
        )
        
        notional = order['amount'] * order['average']
        expected_fee = notional * mock_trader.commission
        
        assert abs(order['fee']['cost'] - expected_fee) < 0.01


class TestMockTraderPositions:
    """Test position management"""
    
    @pytest.mark.asyncio
    async def test_open_long_position(self, mock_trader):
        """Test opening a long position"""
        result = await mock_trader.open_position(
            symbol='BTC/USDT:USDT',
            side='buy',
            amount=0.5,
            leverage=2,
            stop_loss=95.0,
            take_profit=115.0
        )
        
        assert result.main.success == True
        assert result.main.symbol == 'BTC/USDT:USDT'
        
        # Check position exists
        position = await mock_trader.get_position('BTC/USDT:USDT')
        assert position is not None
        assert position.side == 'buy'
        assert position.amount == 0.5
    
    @pytest.mark.asyncio
    async def test_open_short_position(self, mock_trader):
        """Test opening a short position"""
        result = await mock_trader.open_position(
            symbol='ETH/USDT:USDT',
            side='sell',
            amount=1.0
        )
        
        assert result.main.success == True
        
        position = await mock_trader.get_position('ETH/USDT:USDT')
        assert position.side == 'sell'
    
    @pytest.mark.asyncio
    async def test_close_position(self, mock_trader):
        """Test closing a position"""
        # First open a position
        await mock_trader.open_position(
            symbol='BTC/USDT:USDT',
            side='buy',
            amount=0.5
        )
        
        # Close it
        result = await mock_trader.close_position('BTC/USDT:USDT')
        
        assert result.success == True
        
        # Position should be removed
        position = await mock_trader.get_position('BTC/USDT:USDT')
        assert position is None
    
    @pytest.mark.asyncio
    async def test_close_nonexistent_position(self, mock_trader):
        """Test closing a position that doesn't exist"""
        result = await mock_trader.close_position('NONEXISTENT/USDT:USDT')
        
        assert result.success == False
        assert 'No position found' in result.error
    
    @pytest.mark.asyncio
    async def test_get_all_positions(self, mock_trader):
        """Test getting all positions"""
        # Open multiple positions
        await mock_trader.open_position('BTC/USDT:USDT', 'buy', 0.5)
        await mock_trader.open_position('ETH/USDT:USDT', 'sell', 1.0)
        
        positions = await mock_trader.get_positions()
        
        assert len(positions) == 2


class TestMockTraderBalance:
    """Test balance updates"""
    
    @pytest.mark.asyncio
    async def test_balance_decreases_on_buy(self, mock_trader):
        """Test balance decreases when buying"""
        initial_balance = mock_trader.balance
        
        await mock_trader.create_order(
            symbol='BTC/USDT:USDT',
            order_type='market',
            side='buy',
            amount=1.0
        )
        
        assert mock_trader.balance < initial_balance
    
    @pytest.mark.asyncio
    async def test_balance_increases_on_sell(self, mock_trader):
        """Test balance increases when selling (short)"""
        initial_balance = mock_trader.balance
        
        await mock_trader.create_order(
            symbol='BTC/USDT:USDT',
            order_type='market',
            side='sell',
            amount=1.0
        )
        
        # Selling adds to balance (minus fees)
        assert mock_trader.balance > initial_balance
    
    @pytest.mark.asyncio
    async def test_balance_after_round_trip(self, mock_trader):
        """Test balance after buy then sell (should lose to fees)"""
        initial_balance = mock_trader.balance
        
        # Buy
        await mock_trader.open_position('BTC/USDT:USDT', 'buy', 1.0)
        
        # Sell (close)
        await mock_trader.close_position('BTC/USDT:USDT')
        
        # Balance should be less due to commission and slippage
        assert mock_trader.balance < initial_balance


class TestMockTraderDataFetching:
    """Test data fetching methods"""
    
    @pytest.mark.asyncio
    async def test_fetch_ohlcv(self, mock_trader):
        """Test fetching OHLCV data"""
        ohlcv = await mock_trader.fetch_ohlcv('BTC/USDT:USDT', '3m', limit=50)
        
        assert len(ohlcv) > 0
        assert len(ohlcv[0]) == 6  # [timestamp, O, H, L, C, V]
    
    @pytest.mark.asyncio
    async def test_fetch_ohlcv_time_filtering(self, mock_trader):
        """Test OHLCV respects current_time"""
        ohlcv = await mock_trader.fetch_ohlcv('BTC/USDT:USDT', '3m', limit=100)
        
        current_time = mock_trader.data_source.current_time
        
        # All candles should be <= current_time
        for candle in ohlcv:
            assert candle[0] <= current_time
    
    @pytest.mark.asyncio
    async def test_fetch_ticker(self, mock_trader):
        """Test fetch_ticker derives from K-line"""
        ticker = await mock_trader.fetch_ticker('BTC/USDT:USDT')
        
        assert ticker['symbol'] == 'BTC/USDT:USDT'
        assert 'last' in ticker
        assert 'close' in ticker
        assert ticker['last'] > 0
    
    @pytest.mark.asyncio
    async def test_fetch_tickers_batch(self, mock_trader):
        """Test batch ticker fetching"""
        tickers = await mock_trader.fetch_tickers(['BTC/USDT:USDT', 'ETH/USDT:USDT'])
        
        assert 'BTC/USDT:USDT' in tickers
        assert 'ETH/USDT:USDT' in tickers
    
    @pytest.mark.asyncio
    async def test_watch_tickers(self, mock_trader):
        """Test watch_tickers method"""
        tickers = await mock_trader.watch_tickers(['BTC/USDT:USDT'])
        
        assert 'BTC/USDT:USDT' in tickers
        assert tickers['BTC/USDT:USDT']['last'] > 0
    
    @pytest.mark.asyncio
    async def test_fetch_funding_rates(self, mock_trader):
        """Test fetching funding rates"""
        rates = await mock_trader.fetchFundingRates(['BTC/USDT:USDT', 'ETH/USDT:USDT'])
        
        assert 'BTC/USDT:USDT' in rates
        assert 'fundingRate' in rates['BTC/USDT:USDT']


class TestMockTraderAccount:
    """Test account info methods"""
    
    @pytest.mark.asyncio
    async def test_get_account_info(self, mock_trader):
        """Test getting account info"""
        account = await mock_trader.get_account_info()
        
        assert account.total['USDT'] == mock_trader.balance
        assert account.free['USDT'] == mock_trader.balance
    
    @pytest.mark.asyncio
    async def test_account_updates_after_trade(self, mock_trader):
        """Test account reflects trade"""
        await mock_trader.create_order('BTC/USDT:USDT', 'market', 'buy', 0.1)
        
        account = await mock_trader.get_account_info()
        
        assert account.total['USDT'] == mock_trader.balance
        assert account.total['USDT'] < 10000.0  # Less than initial


class TestMockTraderPerformanceIntegration:
    """Test integration with MockPerformanceService"""
    
    @pytest.mark.asyncio
    async def test_trade_recorded_on_close(self, mock_trader):
        """Test trade is recorded when position is closed"""
        # Open position
        await mock_trader.open_position('BTC/USDT:USDT', 'buy', 0.5)
        
        # Close position
        await mock_trader.close_position('BTC/USDT:USDT')
        
        # Check trade was recorded
        if mock_trader.performance_service:
            assert len(mock_trader.performance_service.trades) == 1


class TestMockTraderEdgeCases:
    """Test edge cases and error handling"""
    
    @pytest.mark.asyncio
    async def test_get_price_nonexistent_symbol(self, mock_trader):
        """Test getting price for nonexistent symbol"""
        price = await mock_trader._get_current_price('NONEXISTENT/USDT:USDT')
        
        assert price == 0
    
    @pytest.mark.asyncio
    async def test_close_method(self, mock_trader):
        """Test close method doesn't error"""
        await mock_trader.close()
        # Should complete without error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

