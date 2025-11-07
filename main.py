from src.LangTrader.utils import logger
from src.LangTrader.market import CryptoFetcher
from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from time import sleep
from src.LangTrader.config import Config
from src.LangTrader.ai.decision_engine import DecisionEngine, DecisionEngineState





def main():
    """
    logger.info("Hello from LangTrader!")
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
    """
    """ Strarting LLM test """
    config = Config(trader_id="6e8de582-d12b-434c-b1fa-0ee788590b4d")
    decision_engine = DecisionEngine(config)
    state = DecisionEngineState(
        trader_id=config.trader_id,
        symbol=config.symbols,
        market_data={},
        indicators={},
        postion_info={},
        action=False,
        risk_passed=False,
        confidence=0.0,
        leverage=0,
        llm_analysis="",
    )
    result = decision_engine.run(state)
    logger.info(f"Decision engine result: {result}")

if __name__ == "__main__":
    main()
