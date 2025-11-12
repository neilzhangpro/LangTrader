"""Trader 类单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.trader import Trader


@pytest.fixture
def mock_config():
    """Mock Config 对象"""
    config = MagicMock()
    config.trader_id = "test-trader-123"
    config.symbols = ["BTC", "ETH"]
    config.llm_config = {"openai": {"model": "gpt-4"}}
    config.risk_config = {"max_leverage": 3}
    return config


@pytest.fixture
def mock_positions():
    """Mock positions 数据"""
    return [
        {
            "id": "pos-1",
            "symbol": "BTC",
            "entry_price": 100000.0,
            "exit_price": 102000.0,
            "quantity": 0.01,
            "leverage": 2,
            "realized_pnl": 40.0,
            "status": "closed"
        },
        {
            "id": "pos-2",
            "symbol": "ETH",
            "entry_price": 3000.0,
            "exit_price": 2950.0,
            "quantity": 0.5,
            "leverage": 2,
            "realized_pnl": -50.0,
            "status": "closed"
        }
    ]


class TestTraderInit:
    """Trader 初始化测试"""
    
    @patch('src.LangTrader.trader.Database')
    @patch('src.LangTrader.trader.CryptoFetcher')
    @patch('src.LangTrader.trader.hyperliquidAPI')
    def test_trader_init(self, mock_hl, mock_fetcher, mock_db, mock_config):
        """测试1：Trader 正常初始化"""
        trader = Trader(mock_config)
        
        assert trader.config == mock_config
        assert trader.symbols == ["BTC", "ETH"]
        assert trader.hyperliquid is not None
        assert trader.fetcher is not None
        assert trader.db is not None


class TestGet20PositionInfo:
    """get_20_position_info 方法测试"""
    
    @patch('src.LangTrader.trader.Database')
    @patch('src.LangTrader.trader.CryptoFetcher')
    @patch('src.LangTrader.trader.hyperliquidAPI')
    def test_get_positions_success(self, mock_hl, mock_fetcher, mock_db_class, 
                                   mock_config, mock_positions):
        """测试2：成功获取 positions"""
        mock_db = MagicMock()
        mock_db.execute.return_value = mock_positions
        mock_db_class.return_value = mock_db
        
        trader = Trader(mock_config)
        result = trader.get_20_position_info("test-trader-123")
        
        # 验证返回了 positions
        assert result is not None
        assert len(result) == 2
        assert result[0]["symbol"] == "BTC"
    
    @patch('src.LangTrader.trader.Database')
    @patch('src.LangTrader.trader.CryptoFetcher')
    @patch('src.LangTrader.trader.hyperliquidAPI')
    def test_get_positions_empty(self, mock_hl, mock_fetcher, mock_db_class, mock_config):
        """测试3：没有 positions 时返回 None"""
        mock_db = MagicMock()
        mock_db.execute.return_value = []
        mock_db_class.return_value = mock_db
        
        trader = Trader(mock_config)
        result = trader.get_20_position_info("test-trader-123")
        
        assert result is None
    
    @patch('src.LangTrader.trader.Database')
    @patch('src.LangTrader.trader.CryptoFetcher')
    @patch('src.LangTrader.trader.hyperliquidAPI')
    def test_get_positions_sql_query(self, mock_hl, mock_fetcher, mock_db_class, 
                                    mock_config, mock_positions):
        """测试4：验证 SQL 查询正确"""
        mock_db = MagicMock()
        mock_db.execute.return_value = mock_positions
        mock_db_class.return_value = mock_db
        
        trader = Trader(mock_config)
        trader.get_20_position_info("test-trader-123")
        
        # 验证 SQL 查询被调用
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        
        # 验证查询包含必要的条件
        query = call_args[0][0]
        assert "positions" in query.lower()
        assert "trader_id" in query.lower()
        assert "status = 'closed'" in query.lower()
        assert "limit 20" in query.lower()


class TestTraderIntegration:
    """Trader 集成测试（可选）"""
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="需要真实数据库")
    def test_trader_with_real_db(self):
        """测试5：使用真实数据库"""
        # 这个测试需要真实的数据库连接
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

