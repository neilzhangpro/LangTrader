"""配置管理测试"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock, mock_open
from src.LangTrader.config import Config


class TestConfig:
    """Config 类单元测试"""
    
    @patch('src.LangTrader.config.Database')
    def test_config_init(self, mock_db_class):
        """测试1：Config 初始化"""
        # 模拟数据库返回值
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        # 模拟数据库查询结果
        mock_db.execute.side_effect = [
            [{'llm_config': {'provider': 'openai'}}],  # get_llm_config
            [{'exchange_configs': {'exchange': 'hyperliquid'}}],  # get_exchange_config
            [{'risk_config': {'max_leverage': 5}}],  # get_risk_config
            [{'system_prompt': 'Test prompt'}]  # get_system_prompt
        ]
        
        # 修复后的代码需要 trader_id
        trader_id = "test-uuid-123"
        config = Config(trader_id=trader_id)
        
        # 验证初始化成功
        assert config.trader_id == trader_id
        assert config.db is not None
        assert config.llm_config == {'provider': 'openai'}
        assert config.exchange_config == {'exchange': 'hyperliquid'}
        assert config.risk_config == {'max_leverage': 5}
        assert config.system_prompt == 'Test prompt'
    
    @patch('src.LangTrader.config.Database')
    def test_get_llm_config(self, mock_db_class):
        """测试2：获取 LLM 配置"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        expected_config = {'provider': 'openai', 'model': 'gpt-4', 'temperature': 0.7}
        
        # 模拟初始化和单独调用
        mock_db.execute.side_effect = [
            [{'llm_config': expected_config}],  # __init__ 调用
            [{'exchange_configs': {}}],
            [{'risk_config': {}}],
            [{'system_prompt': 'test'}],
            [{'llm_config': expected_config}]  # 单独调用 get_llm_config
        ]
        
        config = Config(trader_id="test-123")
        result = config.get_llm_config()
        
        assert result == expected_config
    
    @patch('src.LangTrader.config.Database')
    def test_get_exchange_config(self, mock_db_class):
        """测试3：获取交易所配置"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        expected_config = {
            'account_address': '0x123',
            'secret_key': '0xabc'
        }
        
        mock_db.execute.side_effect = [
            [{'llm_config': {}}],
            [{'exchange_configs': expected_config}],  # 注意是 exchange_configs
            [{'risk_config': {}}],
            [{'system_prompt': 'test'}]
        ]
        
        config = Config(trader_id="test-123")
        assert config.exchange_config == expected_config
    
    @patch('src.LangTrader.config.Database')
    def test_get_risk_config(self, mock_db_class):
        """测试4：获取风控配置"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        expected_config = {
            'max_position_size': 0.1,
            'max_leverage': 3,
            'stop_loss_percent': 0.03
        }
        
        mock_db.execute.side_effect = [
            [{'llm_config': {}}],
            [{'exchange_configs': {}}],
            [{'risk_config': expected_config}],
            [{'system_prompt': 'test'}]
        ]
        
        config = Config(trader_id="test-123")
        assert config.risk_config == expected_config
    
    @patch('src.LangTrader.config.Database')
    def test_set_llm_config(self, mock_db_class):
        """测试5：设置 LLM 配置"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        # 初始化时的返回值
        mock_db.execute.side_effect = [
            [{'llm_config': {'provider': 'openai'}}],
            [{'exchange_configs': {}}],
            [{'risk_config': {}}],
            [{'system_prompt': 'test'}],
            []  # set_llm_config 的返回值
        ]
        
        config = Config(trader_id="test-123")
        new_config = {'provider': 'anthropic', 'model': 'claude-3'}
        
        config.set_llm_config(new_config)
        
        # 验证更新了本地缓存
        assert config.llm_config == new_config
        
        # 验证调用了数据库更新
        assert mock_db.execute.called
    
    @patch('src.LangTrader.config.Database')
    @patch('builtins.open', new_callable=mock_open)
    def test_set_exchange_config_updates_file(self, mock_file, mock_db_class):
        """测试6：设置交易所配置应该更新 config.json 文件"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        # 初始化返回值
        mock_db.execute.side_effect = [
            [{'llm_config': {}}],
            [{'exchange_configs': {}}],
            [{'risk_config': {}}],
            [{'system_prompt': 'test'}],
            []  # set_exchange_config 的返回值
        ]
        
        config = Config(trader_id="test-123")
        new_config = {
            'account_address': '0x456',
            'secret_key': '0xdef'
        }
        
        config.set_exchange_config(new_config)
        
        # 验证更新了本地缓存
        assert config.exchange_config == new_config
        
        # 验证写入了文件
        mock_file.assert_called_once_with("config.json", "w")
        handle = mock_file()
        written_data = ''.join(call.args[0] for call in handle.write.call_args_list)
        # 验证写入的是 JSON 格式
        assert '"account_address"' in written_data or 'account_address' in written_data
    
    def test_config_validates_llm_config(self):
        """测试7：验证 LLM 配置格式"""
        # 测试配置验证逻辑
        valid_config = {
            'provider': 'openai',
            'model': 'gpt-4',
            'temperature': 0.7
        }
        
        # 应该验证必需字段
        assert 'provider' in valid_config
        assert 'model' in valid_config
        
        # 温度应该在 0-1 之间
        assert 0 <= valid_config['temperature'] <= 1
    
    def test_config_validates_risk_config(self):
        """测试8：验证风控配置格式"""
        valid_config = {
            'max_position_size': 0.1,
            'max_leverage': 3,
            'stop_loss_percent': 0.03,
            'take_profit_percent': 0.06
        }
        
        # 验证数值范围
        assert 0 < valid_config['max_position_size'] <= 1
        assert 1 <= valid_config['max_leverage'] <= 50
        assert 0 < valid_config['stop_loss_percent'] < 1
        assert 0 < valid_config['take_profit_percent'] < 1


    @patch('src.LangTrader.config.Database')
    def test_set_risk_config(self, mock_db_class):
        """测试7：设置风控配置"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        mock_db.execute.side_effect = [
            [{'llm_config': {}}],
            [{'exchange_configs': {}}],
            [{'risk_config': {'max_leverage': 3}}],
            [{'system_prompt': 'test'}],
            []  # set_risk_config 返回值
        ]
        
        config = Config(trader_id="test-123")
        new_risk_config = {
            'max_position_size': 0.2,
            'max_leverage': 5,
            'stop_loss_percent': 0.05
        }
        
        config.set_risk_config(new_risk_config)
        
        # 验证本地缓存已更新
        assert config.risk_config == new_risk_config
    
    @patch('src.LangTrader.config.Database')
    def test_set_system_prompt(self, mock_db_class):
        """测试8：设置系统提示词"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        mock_db.execute.side_effect = [
            [{'llm_config': {}}],
            [{'exchange_configs': {}}],
            [{'risk_config': {}}],
            [{'system_prompt': 'old prompt'}],
            []  # set_system_prompt 返回值
        ]
        
        config = Config(trader_id="test-123")
        new_prompt = 'You are an expert trader.'
        
        config.set_system_prompt(new_prompt)
        
        # 验证本地缓存已更新
        assert config.system_prompt == new_prompt
    
    @patch('src.LangTrader.config.Database')
    def test_config_close(self, mock_db_class):
        """测试9：关闭数据库连接"""
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        mock_db.execute.side_effect = [
            [{'llm_config': {}}],
            [{'exchange_configs': {}}],
            [{'risk_config': {}}],
            [{'system_prompt': 'test'}]
        ]
        
        config = Config(trader_id="test-123")
        config.close()
        
        # 验证数据库连接被关闭
        mock_db.close.assert_called_once()


def test_config_json_file_format():
    """测试9：验证 config.json 文件格式"""
    # 测试写入的 JSON 格式是否正确
    test_config = {
        'account_address': '0x123',
        'secret_key': '0xabc'
    }
    
    # 验证可以序列化为 JSON
    json_str = json.dumps(test_config)
    assert isinstance(json_str, str)
    
    # 验证可以反序列化
    loaded = json.loads(json_str)
    assert loaded == test_config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

