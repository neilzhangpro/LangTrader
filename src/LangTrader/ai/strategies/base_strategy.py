from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseStrategy:
    def __init__(self, name:str, description:str):
        self.name = name;
        self.description = description
    
    @abstractmethod
    def generate_signal(self, market_data:Dict,position_data):
        pass