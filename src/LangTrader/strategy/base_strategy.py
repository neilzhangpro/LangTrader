from abc import abstractmethod
import pandas as pd

class BaseStrategy:
    def __init__(self, name:str,description:str):
        self.name = name
        self.description = description

    @abstractmethod
    def generate_signal(self, symbol:str, df:pd.DataFrame) -> dict:
        pass