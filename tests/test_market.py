# test market module
from src.LangTrader.market import CryptoFetcher

def test_fetcher_init():
    """Test the initialization of the class is successful"""
    fetcher = CryptoFetcher(symbol="BTC")
    assert fetcher is not None
    assert fetcher.symbol == "BTC"

def test_fetcher_get_current_price():
    """Test the get_current_price method is successful"""
    fetcher = CryptoFetcher(symbol="BTC")
    current_price = fetcher.get_current_price()

    assert current_price is not None
    float_price = float(current_price)
    assert float_price >0
    assert float_price < 1000000