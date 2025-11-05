
from utils import logger
from market import CryptoFetcher
from hyperliquidExchange import hyperliquidAPI
from time import sleep





def main():
    logger.info("Hello from simper-trader!")
    fetcher = CryptoFetcher(symbol="BTC")
    current_price = fetcher.get_current_price()
    df = fetcher.get_OHLCV()
    df = fetcher.get_technical_indicators(df)
    simple_prompt = fetcher.get_simple_trade_signal(df)
    #get the hyperliquid API
    hyperliquid = hyperliquidAPI()
    account_balance = hyperliquid.get_account_balance()
    test_order = hyperliquid.test_order("BTC")
    logger.info(f"Test order result: {test_order}")
    sleep(20)
    close_all_positions = hyperliquid.close_all_positions()
    logger.info(f"Close all positions result: {close_all_positions}")

if __name__ == "__main__":
    main()
