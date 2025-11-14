# 修改 simper-trader/src/LangTrader/db.py
import psycopg2
from psycopg2 import pool
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import threading
import time
load_dotenv()

class Database:
    # 添加连接池类变量
    _connection_pool = None
    _pool_lock = threading.Lock()  # 添加线程锁
    
    @classmethod
    def initialize_connection_pool(cls):
        """初始化连接池"""
        with cls._pool_lock:  # 使用锁确保线程安全
            if cls._connection_pool is None:
                try:
                    cls._connection_pool = psycopg2.pool.SimpleConnectionPool(
                        1,   # 最小连接数
                        50,  # 增加最大连接数到50
                        host=os.getenv("dbHost"),
                        port=os.getenv("dbPort"),
                        database=os.getenv("dbBase"),
                        user=os.getenv("dbUser"),
                        password=os.getenv("dbPass"),
                        connect_timeout=10  # 添加连接超时
                    )
                    print("数据库连接池创建成功")
                except Exception as e:
                    print(f"创建连接池失败: {e}")
                    raise
        return cls._connection_pool
    
    @classmethod
    def get_pool_connection(cls, retry_count=3):
        """从连接池获取连接，带重试机制"""
        if cls._connection_pool is None:
            cls.initialize_connection_pool()
            
        for attempt in range(retry_count):
            try:
                conn = cls._connection_pool.getconn()
                if conn:
                    return conn
            except psycopg2.pool.PoolError as e:
                if attempt < retry_count - 1:
                    print(f"获取连接失败，{2 ** attempt}秒后重试: {e}")
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    raise
            except Exception as e:
                print(f"获取连接时发生未知错误: {e}")
                raise
        
        raise psycopg2.pool.PoolError("无法从连接池获取连接")
    
    @classmethod
    def return_pool_connection(cls, conn):
        """将连接返回给连接池"""
        if cls._connection_pool and conn:
            try:
                cls._connection_pool.putconn(conn)
            except Exception as e:
                print(f"返回连接到连接池时出错: {e}")
    
    @classmethod
    def close_all_connections(cls):
        """关闭所有连接"""
        with cls._pool_lock:
            if cls._connection_pool:
                try:
                    cls._connection_pool.closeall()
                    print("所有数据库连接已关闭")
                except Exception as e:
                    print(f"关闭连接池时出错: {e}")
                finally:
                    cls._connection_pool = None
    
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.get_connection_from_pool()
    
    def get_connection_from_pool(self):
        """从连接池获取连接"""
        try:
            self.conn = Database.get_pool_connection()
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            print(f"从连接池获取连接失败: {e}")
            raise
    
    def execute(self, query, params=None):
        try:
            if not self.conn or self.conn.closed:
                # 如果连接已关闭，重新获取连接
                self.get_connection_from_pool()
                
            self.cursor.execute(query, params)
            self.conn.commit()
            if self.cursor.description:
                return self.cursor.fetchall()
            return []
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            print(f"执行查询失败: {e}")
            raise
    
    def close(self):
        """将连接返回给连接池而不是关闭"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                Database.return_pool_connection(self.conn)
        except Exception as e:
            print(f"返回连接到连接池时出错: {e}")
    
    @classmethod
    def get_pool_status(cls):
        """获取连接池状态"""
        if cls._connection_pool:
            return {
                'minconn': cls._connection_pool.minconn,
                'maxconn': cls._connection_pool.maxconn,
                'used': len(cls._connection_pool._used),
                'free': len(cls._connection_pool._pool)
            }
        return None