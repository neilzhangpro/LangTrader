"""数据库连接测试"""

import pytest
import psycopg2
from unittest.mock import Mock, patch, MagicMock
from src.LangTrader.db import Database


class TestDatabase:
    """数据库类测试"""
    
    def test_database_init_with_env(self):
        """测试1：使用环境变量初始化数据库连接"""
        with patch.dict('os.environ', {
            'dbHost': 'localhost',
            'dbPort': '5432',
            'dbBase': 'langtrader',
            'dbUser': 'postgres',
            'dbPass': 'testpass'
        }):
            with patch('psycopg2.connect') as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value = mock_conn
                
                db = Database()
                
                # 验证连接参数
                mock_connect.assert_called_once()
                assert db.conn is not None
    
    def test_execute_query(self):
        """测试2：执行查询"""
        with patch('psycopg2.connect') as mock_connect:
            # 模拟数据库连接和游标
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # 模拟查询结果
            mock_cursor.fetchall.return_value = [
                {'id': '123', 'name': 'Test Trader'}
            ]
            
            with patch.dict('os.environ', {
                'dbHost': 'localhost',
                'dbPort': '5432',
                'dbBase': 'langtrader',
                'dbUser': 'postgres',
                'dbPass': 'test'
            }):
                db = Database()
                result = db.execute("SELECT * FROM traders")
                
                # 验证查询被执行
                mock_cursor.execute.assert_called_once_with("SELECT * FROM traders", None)
                mock_conn.commit.assert_called_once()
                
                # 验证返回结果
                assert len(result) == 1
                assert result[0]['name'] == 'Test Trader'
    
    def test_execute_query_with_params(self):
        """测试3：执行带参数的查询"""
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            mock_cursor.fetchall.return_value = []
            
            with patch.dict('os.environ', {
                'dbHost': 'localhost',
                'dbPort': '5432',
                'dbBase': 'langtrader',
                'dbUser': 'postgres',
                'dbPass': 'test'
            }):
                db = Database()
                query = "INSERT INTO traders (name) VALUES (%s)"
                params = ("Test",)
                
                db.execute(query, params)
                
                # 验证参数被正确传递
                mock_cursor.execute.assert_called_once_with(query, params)
    
    def test_close_connection(self):
        """测试4：关闭连接"""
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            with patch.dict('os.environ', {
                'dbHost': 'localhost',
                'dbPort': '5432',
                'dbBase': 'langtrader',
                'dbUser': 'postgres',
                'dbPass': 'test'
            }):
                db = Database()
                db.close()
                
                # 验证连接和游标被关闭
                mock_cursor.close.assert_called_once()
                mock_conn.close.assert_called_once()
    
    def test_connection_error(self):
        """测试5：连接失败时的错误处理"""
        with patch('psycopg2.connect') as mock_connect:
            # 模拟连接失败
            mock_connect.side_effect = psycopg2.OperationalError("无法连接到数据库")
            
            with patch.dict('os.environ', {
                'dbHost': 'invalid_host',
                'dbPort': '5432',
                'dbBase': 'langtrader',
                'dbUser': 'postgres',
                'dbPass': 'test'
            }):
                # 验证抛出异常
                with pytest.raises(psycopg2.OperationalError):
                    db = Database()



if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])

