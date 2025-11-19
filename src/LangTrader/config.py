#config class for LLM & Dex

import json
import os
from src.LangTrader.db import Database

class Config:
    """Config class for LLM & Dex"""
    def __init__(self, trader_id: str):
        """
        初始化配置
        
        Args:
            trader_id: 交易员 ID (UUID)
        """
        self.trader_id = trader_id
        # 使用连接池的数据库连接
        self.db = Database()
        
        # 从数据库加载配置
        self.llm_config = self.get_llm_config()
        self.exchange_config = self.get_exchange_config()
        self.risk_config = self.get_risk_config()
        self.system_prompt = self.get_system_prompt()
        self.symbols = self.get_symbols()
        
        # 🆕 加载自定义提示词配置
        self.custom_system_prompt = self.get_custom_system_prompt()
        self.custom_user_prompt = self.get_custom_user_prompt()
    
    def get_symbols(self):
        """获取符号配置"""
        query = "SELECT symbols FROM traders WHERE id = %s"
        params = (self.trader_id,)
        result = self.db.execute(query, params)
        return result[0]['symbols'] if result else None
    
    def get_llm_config(self):
        """获取 LLM 配置"""
        query = "SELECT llm_config FROM traders WHERE id = %s"
        params = (self.trader_id,)
        result = self.db.execute(query, params)
        return result[0]['llm_config'] if result else None
    
    def get_exchange_config(self):
        """获取交易所配置"""
        query = "SELECT exchange_configs FROM traders WHERE id = %s"
        params = (self.trader_id,)
        result = self.db.execute(query, params)
        return result[0]['exchange_configs'] if result else None
    
    def get_risk_config(self):
        """获取风控配置"""
        query = "SELECT risk_config FROM traders WHERE id = %s"
        params = (self.trader_id,)
        result = self.db.execute(query, params)
        return result[0]['risk_config'] if result else None
    
    def get_system_prompt(self):
        """获取系统提示词"""
        query = "SELECT system_prompt FROM traders WHERE id = %s"
        params = (self.trader_id,)
        result = self.db.execute(query, params)
        return result[0]['system_prompt'] if result else None
    
    def get_custom_system_prompt(self):
        """获取自定义系统提示词"""
        query = "SELECT custom_system_prompt FROM traders WHERE id = %s"
        params = (self.trader_id,)
        result = self.db.execute(query, params)
        return result[0]['custom_system_prompt'] if result and result[0].get('custom_system_prompt') else None
    
    def get_custom_user_prompt(self):
        """获取自定义用户提示词模板"""
        query = "SELECT custom_user_prompt FROM traders WHERE id = %s"
        params = (self.trader_id,)
        result = self.db.execute(query, params)
        return result[0]['custom_user_prompt'] if result and result[0].get('custom_user_prompt') else None

    def set_llm_config(self, llm_config):
        """设置 LLM 配置"""
        query = "UPDATE traders SET llm_config = %s WHERE id = %s"
        params = (json.dumps(llm_config) if isinstance(llm_config, dict) else llm_config, self.trader_id)
        result = self.db.execute(query, params)
        # 更新本地缓存
        self.llm_config = llm_config
        return result
    
    def set_exchange_config(self, exchange_config):
        """设置交易所配置"""
        query = "UPDATE traders SET exchange_configs = %s WHERE id = %s"
        params = (json.dumps(exchange_config) if isinstance(exchange_config, dict) else exchange_config, self.trader_id)
        result = self.db.execute(query, params)
        # 更新本地缓存
        self.exchange_config = exchange_config
        # 同时更新本地 config.json 文件
        try:
            with open("config.json", "w") as f:
                json.dump(exchange_config, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to update config.json: {e}")
        return result
    
    def set_risk_config(self, risk_config):
        """设置风控配置"""
        query = "UPDATE traders SET risk_config = %s WHERE id = %s"
        params = (json.dumps(risk_config) if isinstance(risk_config, dict) else risk_config, self.trader_id)
        result = self.db.execute(query, params)
        # 更新本地缓存
        self.risk_config = risk_config
        return result
    
    def set_system_prompt(self, system_prompt):
        """设置系统提示词"""
        query = "UPDATE traders SET system_prompt = %s WHERE id = %s"
        params = (system_prompt, self.trader_id)
        result = self.db.execute(query, params)
        # 更新本地缓存
        self.system_prompt = system_prompt
        return result
    
    def set_custom_prompts(self, custom_system_prompt=None, custom_user_prompt=None):
        """设置自定义提示词"""
        query = "UPDATE traders SET custom_system_prompt = %s, custom_user_prompt = %s WHERE id = %s"
        params = (custom_system_prompt, custom_user_prompt, self.trader_id)
        result = self.db.execute(query, params)
        # 更新本地缓存
        self.custom_system_prompt = custom_system_prompt
        self.custom_user_prompt = custom_user_prompt
        return result
    
    def close(self):
        """将数据库连接返回给连接池"""
        if self.db:
            self.db.close()