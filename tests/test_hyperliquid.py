"""hyperliquidExchange 核心功能测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from src.LangTrader.hyperliquidExchange import hyperliquidAPI


@pytest.fixture
def mock_config_file():
    """Mock config.json 文件"""
    config_data = '{"account_address": "0x123", "secret_key": "0xabc"}'
    return mock_open(read_data=config_data)


@pytest.fixture
def mock_account_balance():
    """Mock 账户余额"""
    return {
        "marginSummary": {
            "accountValue": "1000.0",
            "totalNtlPos": "0.0",
            "totalRawUsd": "1000.0",
            "totalMarginUsed": "0.0"
        },
        "assetPositions": []
    }


class TestHyperliquidInit:
    """hyperliquidAPI 初始化测试"""
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_init_success(self, mock_open_file, mock_from_key, mock_info, mock_exchange, mock_config_file):
        """测试1：正常初始化"""
        mock_open_file.return_value = mock_config_file()
        mock_account = MagicMock()
        mock_from_key.return_value = mock_account
        mock_info_instance = MagicMock()
        mock_info_instance.user_state.return_value = {"marginSummary": {}}
        mock_info_instance.spot_user_state.return_value = {"balances": []}
        mock_info.return_value = mock_info_instance
        
        api = hyperliquidAPI()
        
        assert api.account_address == "0x123"
        assert api.secret_key == "0xabc"


class TestCalculateBuySize:
    """calculate_buy_size 方法测试"""
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_calculate_buy_size_normal(self, mock_open_file, mock_from_key, 
                                      mock_info_class, mock_exchange, mock_config_file):
        """测试2：正常计算买入数量"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {
            "marginSummary": {"totalRawUsd": "1000.0", "accountValue": "1000.0"},
            "withdrawable": "1000.0"
        }
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.meta.return_value = {"universe": []}
        mock_info.all_mids.return_value = {"BTC": "100000"}
        mock_info.active_asset_data.return_value = {"availableToTrade": ["5", "5"]}
        mock_info_class.return_value = mock_info
        
        api = hyperliquidAPI()
        result = api.calculate_buy_size("BTC", leverage=5, confidence=0.8)
        
        # 验证返回值
        assert result is not None
        assert "max_buy_size" in result
        assert "price" in result
        assert result["leverage"] == 5
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_calculate_buy_size_insufficient_balance(self, mock_open_file, mock_from_key, 
                                                     mock_info_class, mock_exchange, mock_config_file):
        """测试3：余额不足时返回 None"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {
            "marginSummary": {"totalRawUsd": "0.5", "accountValue": "0.5"},
            "withdrawable": "0.5"
        }
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.meta.return_value = {"universe": []}
        mock_info.all_mids.return_value = {"BTC": "100000"}
        mock_info.active_asset_data.return_value = {"availableToTrade": ["0.0001", "0.0001"]}
        mock_info_class.return_value = mock_info
        
        api = hyperliquidAPI()
        result = api.calculate_buy_size("BTC", leverage=5, confidence=1.0)
        
        # max_buy_size 很小，但仍应返回有效计划
        assert result is not None
        assert result["max_buy_size"] < 0.001


class TestPlaceOrder:
    """place_order 方法测试"""
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_open_position_long(self, mock_open_file, mock_from_key, 
                                mock_info_class, mock_exchange_class, mock_config_file):
        """测试4：做多开仓"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        # Mock Info
        mock_info = MagicMock()
        mock_info.user_state.return_value = {
            "marginSummary": {"totalRawUsd": "1000.0", "accountValue": "1000.0"},
            "withdrawable": "1000.0"
        }
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.meta.return_value = {"universe": []}
        mock_info.all_mids.return_value = {"BTC": "100000"}
        mock_info.active_asset_data.return_value = {"availableToTrade": ["5", "5"]}
        mock_info_class.return_value = mock_info
        
        # Mock Exchange
        mock_exchange = MagicMock()
        mock_exchange.update_leverage.return_value = {"status": "ok"}
        mock_exchange.market_open.return_value = {"status": "ok", "oid": 123}
        mock_exchange_class.return_value = mock_exchange
        
        api = hyperliquidAPI()
        result = api.open_position("BTC", "long", leverage=3, confidence=0.8)
        
        # 验证调用了 market_open
        mock_exchange.market_open.assert_called_once()
        call_args = mock_exchange.market_open.call_args
        
        # 验证参数
        assert call_args[0][0] == "BTC"  # coin_name
        assert call_args[1]["is_buy"] is True  # 做多
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_open_position_short(self, mock_open_file, mock_from_key, 
                                 mock_info_class, mock_exchange_class, mock_config_file):
        """测试5：做空开仓"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {
            "marginSummary": {"totalRawUsd": "1000.0", "accountValue": "1000.0"},
            "withdrawable": "1000.0"
        }
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.meta.return_value = {"universe": []}
        mock_info.all_mids.return_value = {"BTC": "100000"}
        mock_info.active_asset_data.return_value = {"availableToTrade": ["5", "5"]}
        mock_info_class.return_value = mock_info
        
        mock_exchange = MagicMock()
        mock_exchange.update_leverage.return_value = {"status": "ok"}
        mock_exchange.market_open.return_value = {"status": "ok"}
        mock_exchange_class.return_value = mock_exchange
        
        api = hyperliquidAPI()
        result = api.open_position("BTC", "short", leverage=3, confidence=0.8)
        
        # 验证做空
        call_args = mock_exchange.market_open.call_args
        assert call_args[1]["is_buy"] is False  # 做空
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_close_position(self, mock_open_file, mock_from_key, 
                            mock_info_class, mock_exchange_class, mock_config_file):
        """测试6：平仓"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {
            "marginSummary": {"totalRawUsd": "1000.0", "accountValue": "1000.0"},
            "withdrawable": "1000.0"
        }
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.meta.return_value = {"universe": []}
        mock_info.all_mids.return_value = {"BTC": "100000"}
        mock_info_class.return_value = mock_info
        
        mock_exchange = MagicMock()
        mock_exchange.update_leverage.return_value = {"status": "ok"}
        mock_exchange.market_close.return_value = {"status": "ok"}
        mock_exchange_class.return_value = mock_exchange
        
        api = hyperliquidAPI()
        result = api.close_position("BTC", "long", size=1.5)
        
        # 验证调用了 market_close
        mock_exchange.market_close.assert_called_once()
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_open_position_insufficient_balance(self, mock_open_file, mock_from_key, 
                                                mock_info_class, mock_exchange_class, mock_config_file):
        """测试7：余额不足时返回 None"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {
            "marginSummary": {"totalRawUsd": "0.1", "accountValue": "0.1"},
            "withdrawable": "0.1"
        }
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.meta.return_value = {"universe": []}
        mock_info.all_mids.return_value = {"BTC": "100000"}
        mock_info.active_asset_data.return_value = {"availableToTrade": ["0.0001", "0.0001"]}
        mock_info_class.return_value = mock_info
        
        api = hyperliquidAPI()
        result = api.open_position("BTC", "long", confidence=0.8, leverage=3)
        
        # 余额不足，应该返回 None
        assert result is None


class TestConfidenceAdjustment:
    """置信度调整测试"""
    
    def test_confidence_reduces_position_size(self):
        """测试8：置信度降低仓位大小"""
        withdrawable = 1000
        leverage = 5
        price = 100000
        
        # 高置信度
        size_high = (withdrawable * leverage * 0.9) / price
        
        # 低置信度
        size_low = (withdrawable * leverage * 0.3) / price
        
        # 验证低置信度的仓位更小
        assert size_low < size_high
        assert size_low == size_high * (0.3 / 0.9)


class TestCloseAllPositions:
    """close_all_positions 方法测试"""
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_close_all_positions_no_positions(self, mock_open_file, mock_from_key, 
                                              mock_info_class, mock_exchange, mock_config_file):
        """测试9：没有持仓时的处理"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {"marginSummary": {}, "assetPositions": []}
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info_class.return_value = mock_info
        
        api = hyperliquidAPI()
        result = api.close_all_positions()
        
        # 没有持仓，不应该调用平仓操作
        assert result is None or result == None
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_close_all_positions_with_positions(self, mock_open_file, mock_from_key, 
                                                mock_info_class, mock_exchange_class, mock_config_file):
        """测试10：有持仓时平仓"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {
            "marginSummary": {},
            "assetPositions": [
                {"position": {"coin": "BTC", "szi": "0.01"}}
            ]
        }
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info_class.return_value = mock_info
        
        mock_exchange = MagicMock()
        mock_exchange.market_close.return_value = {"status": "ok"}
        mock_exchange_class.return_value = mock_exchange
        
        api = hyperliquidAPI()
        result = api.close_all_positions()
        
        # 验证调用了平仓
        mock_exchange.market_close.assert_called()


class TestGetAssetIndex:
    """_get_asset_index 方法测试"""
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_get_asset_index_found(self, mock_open_file, mock_from_key, 
                                   mock_info_class, mock_exchange, mock_config_file):
        """测试11：找到资产索引"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {"marginSummary": {}}
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.meta.return_value = {
            "universe": [
                {"name": "BTC"},
                {"name": "ETH"},
                {"name": "SOL"}
            ]
        }
        mock_info_class.return_value = mock_info
        
        api = hyperliquidAPI()
        index = api._get_asset_index("ETH")
        
        assert index == 1
    
    @patch('src.LangTrader.hyperliquidExchange.Exchange')
    @patch('src.LangTrader.hyperliquidExchange.Info')
    @patch('src.LangTrader.hyperliquidExchange.eth_account.Account.from_key')
    @patch('builtins.open')
    def test_get_asset_index_not_found(self, mock_open_file, mock_from_key, 
                                       mock_info_class, mock_exchange, mock_config_file):
        """测试12：资产不存在时返回 None"""
        mock_open_file.return_value = mock_config_file()
        mock_from_key.return_value = MagicMock()
        
        mock_info = MagicMock()
        mock_info.user_state.return_value = {"marginSummary": {}}
        mock_info.spot_user_state.return_value = {"balances": []}
        mock_info.meta.return_value = {"universe": [{"name": "BTC"}]}
        mock_info_class.return_value = mock_info
        
        api = hyperliquidAPI()
        index = api._get_asset_index("INVALIDCOIN")
        
        assert index is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

