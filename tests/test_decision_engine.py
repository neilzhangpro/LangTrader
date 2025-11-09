"""DecisionEngine 单元测试"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.ai.decision_engine import DecisionEngine, DecisionEngineState


@pytest.fixture
def mock_config():
    """Mock Config 对象"""
    config = MagicMock()
    config.trader_id = "test-trader-123"
    config.llm_config = {
        "openai": {
            "model": "gpt-4",
            "api_key": "test-key",
            "base_url": "https://api.openai.com/v1"
        }
    }
    config.risk_config = {
        "max_position_size": 0.1,
        "max_leverage": 3,
        "stop_loss_percent": 0.03,
        "take_profit_percent": 0.06
    }
    config.system_prompt = "You are a professional trader."
    return config


@pytest.fixture
def mock_account_balance():
    """Mock 账户余额数据"""
    return {
        "marginSummary": {
            "accountValue": "1000.0",
            "totalNtlPos": "50.0",
            "totalRawUsd": "950.0",
            "totalMarginUsed": "100.0"
        },
        "assetPositions": []
    }


@pytest.fixture
def test_state():
    """测试用的初始状态"""
    return {
        "trader_id": "test-123",
        "symbol": "BTC",
        "market_data": {"price": 100000},
        "indicators": {"RSI_14": 50},
        "postion_info": {},
        "action": False,
        "risk_passed": False,
        "confidence": 0.0,
        "leverage": 2,
        "llm_analysis": ""
    }


class TestDecisionEngineInit:
    """DecisionEngine 初始化测试"""
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_init_success(self, mock_init_model, mock_exchange_class, mock_config):
        """测试1：正常初始化"""
        mock_model = MagicMock()
        mock_init_model.return_value = mock_model
        mock_exchange = MagicMock()
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        
        assert engine.config == mock_config
        assert engine.model == mock_model
        assert engine.hyperliquid == mock_exchange
        assert engine.runner is not None
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_init_with_correct_model_params(self, mock_init_model, mock_exchange_class, mock_config):
        """测试2：验证 LLM 初始化参数"""
        mock_init_model.return_value = MagicMock()
        mock_exchange_class.return_value = MagicMock()
        
        engine = DecisionEngine(mock_config)
        
        # 验证调用参数
        mock_init_model.assert_called_once_with(
            model="gpt-4",
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )


class TestRiskCheck:
    """风险检查节点测试"""
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_pass(self, mock_init_model, mock_exchange_class, 
                            mock_config, mock_account_balance, test_state):
        """测试3：风险检查通过"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        mock_exchange.get_account_balance.return_value = mock_account_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        assert result["risk_passed"] is True
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_fail_no_balance(self, mock_init_model, mock_exchange_class, 
                                       mock_config, test_state):
        """测试4：余额为空时失败"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        mock_exchange.get_account_balance.return_value = None
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        assert result["risk_passed"] is False
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_fail_low_balance(self, mock_init_model, mock_exchange_class, 
                                        mock_config, test_state):
        """测试5：余额不足 $10 时失败"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        
        low_balance = {
            "marginSummary": {
                "accountValue": "5.0",
                "totalNtlPos": "0.0",
                "totalRawUsd": "5.0",
                "totalMarginUsed": "0.0"
            }
        }
        mock_exchange.get_account_balance.return_value = low_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        assert result["risk_passed"] is False
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_fail_position_over_limit(self, mock_init_model, mock_exchange_class, 
                                                 mock_config, test_state):
        """测试6：仓位占比超限时失败"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        
        # 仓位占比 = 200 / 1000 = 20% > 10%
        over_position_balance = {
            "marginSummary": {
                "accountValue": "1000.0",
                "totalNtlPos": "200.0",
                "totalRawUsd": "800.0",
                "totalMarginUsed": "50.0"
            }
        }
        mock_exchange.get_account_balance.return_value = over_position_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        assert result["risk_passed"] is False
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_fail_leverage_over_limit(self, mock_init_model, mock_exchange_class, 
                                                 mock_config, mock_account_balance, test_state):
        """测试7：杠杆超限时失败"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        mock_exchange.get_account_balance.return_value = mock_account_balance
        mock_exchange_class.return_value = mock_exchange
        
        # 设置超限杠杆
        test_state["leverage"] = 10  # > max_leverage (3)
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        assert result["risk_passed"] is False
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_fail_margin_over_limit(self, mock_init_model, mock_exchange_class, 
                                               mock_config, test_state):
        """测试8：保证金使用率超85%时失败"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        
        # 保证金使用率 = 900 / 1000 = 90% > 85%
        high_margin_balance = {
            "marginSummary": {
                "accountValue": "1000.0",
                "totalNtlPos": "50.0",
                "totalRawUsd": "100.0",
                "totalMarginUsed": "900.0"
            }
        }
        mock_exchange.get_account_balance.return_value = high_margin_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        assert result["risk_passed"] is False


class TestMarketAnalysis:
    """市场分析节点测试"""
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_market_analysis_returns_market_data(self, mock_init_model, mock_exchange_class, 
                                                 mock_config, test_state):
        """测试9：市场分析返回市场数据"""
        mock_init_model.return_value = MagicMock()
        mock_exchange_class.return_value = MagicMock()
        
        engine = DecisionEngine(mock_config)
        result = engine._market_analysis(test_state)
        
        assert "market_data" in result
        assert result["market_data"] == test_state["market_data"]


class TestLLMAnalysis:
    """LLM 分析节点测试"""
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_llm_analysis_invokes_model(self, mock_init_model, mock_exchange_class, 
                                       mock_config, test_state):
        """测试10：LLM 分析调用模型"""
        mock_model = MagicMock()
        mock_model.invoke.return_value = "BUY signal"
        mock_init_model.return_value = mock_model
        mock_exchange_class.return_value = MagicMock()
        
        engine = DecisionEngine(mock_config)
        result = engine._llm_analysis(test_state)
        
        # 验证模型被调用
        mock_model.invoke.assert_called_once()
        
        # 验证返回必需字段
        assert "llm_analysis" in result
        assert "confidence" in result
        assert "leverage" in result
        assert "action" in result


class TestDecisionEngineWorkflow:
    """完整工作流测试"""
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_full_workflow_with_risk_pass(self, mock_init_model, mock_exchange_class, 
                                         mock_config, mock_account_balance, test_state):
        """测试11：完整工作流 - 风险检查通过"""
        # Mock LLM
        mock_model = MagicMock()
        mock_model.invoke.return_value = "Analysis result"
        mock_init_model.return_value = mock_model
        
        # Mock Exchange
        mock_exchange = MagicMock()
        mock_exchange.get_account_balance.return_value = mock_account_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine.run(test_state)
        
        # 验证最终结果包含必需字段
        assert "risk_passed" in result
        assert "llm_analysis" in result
        assert result["risk_passed"] is True
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_full_workflow_with_risk_fail(self, mock_init_model, mock_exchange_class, 
                                         mock_config, test_state):
        """测试12：完整工作流 - 风险检查失败"""
        mock_init_model.return_value = MagicMock()
        
        # Mock 余额不足
        mock_exchange = MagicMock()
        low_balance = {
            "marginSummary": {
                "accountValue": "5.0",
                "totalNtlPos": "0.0",
                "totalRawUsd": "5.0",
                "totalMarginUsed": "0.0"
            }
        }
        mock_exchange.get_account_balance.return_value = low_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine.run(test_state)
        
        # 风险检查失败，应该在第一个节点就停止
        assert result["risk_passed"] is False


class TestRiskCheckEdgeCases:
    """风险检查边界情况测试"""
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_exactly_at_limit(self, mock_init_model, mock_exchange_class, 
                                        mock_config, test_state):
        """测试13：刚好达到限制"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        
        # 仓位占比刚好 10%
        edge_balance = {
            "marginSummary": {
                "accountValue": "1000.0",
                "totalNtlPos": "100.0",  # 刚好 10%
                "totalRawUsd": "900.0",
                "totalMarginUsed": "50.0"
            }
        }
        mock_exchange.get_account_balance.return_value = edge_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        # >= 10% 应该失败
        assert result["risk_passed"] is False
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_margin_exactly_85_percent(self, mock_init_model, mock_exchange_class, 
                                                  mock_config, test_state):
        """测试14：保证金使用率刚好 85%"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        
        # 保证金使用率 = 850 / 1000 = 85%
        edge_margin_balance = {
            "marginSummary": {
                "accountValue": "1000.0",
                "totalNtlPos": "50.0",
                "totalRawUsd": "150.0",
                "totalMarginUsed": "850.0"
            }
        }
        mock_exchange.get_account_balance.return_value = edge_margin_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        # 刚好 85% 应该通过（> 0.85 才失败）
        assert result["risk_passed"] is True
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_zero_leverage(self, mock_init_model, mock_exchange_class, 
                                     mock_config, mock_account_balance, test_state):
        """测试15：零杠杆（边界情况）"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        mock_exchange.get_account_balance.return_value = mock_account_balance
        mock_exchange_class.return_value = mock_exchange
        
        test_state["leverage"] = 0
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        # 0 <= 3，应该通过
        assert result["risk_passed"] is True
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_account_value_zero(self, mock_init_model, mock_exchange_class, 
                                          mock_config, test_state):
        """测试16：账户价值为0的边界情况"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        
        zero_value_balance = {
            "marginSummary": {
                "accountValue": "0.0",
                "totalNtlPos": "0.0",
                "totalRawUsd": "0.0",
                "totalMarginUsed": "0.0"
            }
        }
        mock_exchange.get_account_balance.return_value = zero_value_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        # totalRawUsd 为 0 < 10，应该失败
        assert result["risk_passed"] is False


class TestStatePreservation:
    """状态保留测试"""
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_risk_check_preserves_state(self, mock_init_model, mock_exchange_class, 
                                       mock_config, mock_account_balance, test_state):
        """测试17：风险检查保留原始状态"""
        mock_init_model.return_value = MagicMock()
        mock_exchange = MagicMock()
        mock_exchange.get_account_balance.return_value = mock_account_balance
        mock_exchange_class.return_value = mock_exchange
        
        engine = DecisionEngine(mock_config)
        result = engine._risk_check(test_state)
        
        # 验证原始状态字段被保留
        assert result["trader_id"] == test_state["trader_id"]
        assert result["symbol"] == test_state["symbol"]
        assert result["market_data"] == test_state["market_data"]
        assert result["leverage"] == test_state["leverage"]
    
    @patch('src.LangTrader.ai.decision_engine.hyperliquidAPI')
    @patch('src.LangTrader.ai.decision_engine.init_chat_model')
    def test_market_analysis_preserves_state(self, mock_init_model, mock_exchange_class, 
                                            mock_config, test_state):
        """测试18：市场分析保留状态"""
        mock_init_model.return_value = MagicMock()
        mock_exchange_class.return_value = MagicMock()
        
        engine = DecisionEngine(mock_config)
        result = engine._market_analysis(test_state)
        
        # 应该返回包含 market_data 的结果
        assert "market_data" in result


class TestRiskConfigValidation:
    """风控配置验证测试"""
    
    def test_risk_config_values_in_valid_range(self):
        """测试19：验证风控配置值在合理范围"""
        risk_config = {
            "max_position_size": 0.1,
            "max_leverage": 3,
            "stop_loss_percent": 0.03,
            "take_profit_percent": 0.06
        }
        
        # max_position_size 应该在 0-1 之间
        assert 0 < risk_config["max_position_size"] <= 1
        
        # max_leverage 应该 >= 1
        assert risk_config["max_leverage"] >= 1
        
        # stop_loss_percent 应该 > 0
        assert risk_config["stop_loss_percent"] > 0
        
        # take_profit > stop_loss (盈亏比 > 1)
        assert risk_config["take_profit_percent"] > risk_config["stop_loss_percent"]
    
    def test_profit_to_loss_ratio(self):
        """测试20：验证盈亏比合理"""
        risk_config = {
            "stop_loss_percent": 0.03,
            "take_profit_percent": 0.06
        }
        
        ratio = risk_config["take_profit_percent"] / risk_config["stop_loss_percent"]
        
        # 盈亏比应该 >= 1.5
        assert ratio >= 1.5, f"盈亏比 {ratio:.2f} 太低"


class TestDecisionEngineStateType:
    """DecisionEngineState 类型测试"""
    
    def test_state_has_required_fields(self, test_state):
        """测试21：验证状态包含所有必需字段"""
        required_fields = [
            "trader_id", "symbol", "market_data", "indicators",
            "postion_info", "action", "risk_passed", 
            "confidence", "leverage", "llm_analysis"
        ]
        
        for field in required_fields:
            assert field in test_state, f"缺少必需字段: {field}"
    
    def test_state_field_types(self, test_state):
        """测试22：验证状态字段类型"""
        assert isinstance(test_state["trader_id"], str)
        assert isinstance(test_state["symbol"], str)
        assert isinstance(test_state["market_data"], dict)
        assert isinstance(test_state["indicators"], dict)
        assert isinstance(test_state["action"], bool)
        assert isinstance(test_state["confidence"], float)
        assert isinstance(test_state["leverage"], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

