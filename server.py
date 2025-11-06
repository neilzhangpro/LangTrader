#creat api server
from fastapi import FastAPI
from src.LangTrader.config import Config
from typing import Optional
from src.LangTrader.market import CryptoFetcher
import pandas as pd
from src.LangTrader.utils import logger
from src.LangTrader.market import CryptoFetcher
from src.LangTrader.hyperliquidExchange import hyperliquidAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/market")
async def get_market(symbol: str):
    """获取市场数据和交易信号"""
    fetcher = CryptoFetcher(symbol=symbol)
    current_price = fetcher.get_current_price()
    df = fetcher.get_OHLCV()
    df = fetcher.get_technical_indicators(df)
    simple_prompt = fetcher.get_simple_trade_signal(df)
    
    # 提取最新的关键指标
    last_row = df.iloc[-1]
    
    # 创建干净的响应数据
    indicators = {
        "rsi": float(last_row.get('RSI_14', 0)) if not pd.isna(last_row.get('RSI_14')) else None,
        "macd": float(last_row.get('MACD_12_26_9', 0)) if not pd.isna(last_row.get('MACD_12_26_9')) else None,
        "macd_signal": float(last_row.get('MACDs_12_26_9', 0)) if not pd.isna(last_row.get('MACDs_12_26_9')) else None,
        "sma_20": float(last_row.get('SMA_20', 0)) if not pd.isna(last_row.get('SMA_20')) else None,
        "ema_20": float(last_row.get('EMA_20', 0)) if not pd.isna(last_row.get('EMA_20')) else None,
    }
    
    return {
        "symbol": symbol,
        "current_price": current_price,
        "indicators": indicators,
        "signal": simple_prompt
    }

@app.get("/hyperliquidBalance")
async def get_hyperliquid_balance():
    hyperliquid = hyperliquidAPI()
    balance = hyperliquid.get_account_balance()
    return {
        "balance": hyperliquid.contract_balance,
        "spot_balance": hyperliquid.spot_balance
    }

@app.post("/hyperliquidTestOrder")
async def post_hyperliquid_test_order(symbol: str):
    hyperliquid = hyperliquidAPI()
    order = hyperliquid.test_order(symbol)
    return {
        "order": order
    }

@app.post("/hyperliquidCloseAllPositions")
async def post_hyperliquid_close_all_positions():
    hyperliquid = hyperliquidAPI()
    positions = hyperliquid.close_all_positions()
    return {
        "positions": positions
    }

@app.post("/hyperliquidClosePosition")
async def post_hyperliquid_close_position(symbol: str):
    hyperliquid = hyperliquidAPI()
    position = hyperliquid.close_position(symbol)
    return {
        "position": position
    }

@app.post("/hyperliquidUpdateLeverage")
async def post_hyperliquid_update_leverage(symbol: str, leverage: int):
    hyperliquid = hyperliquidAPI()
    leverage = hyperliquid.update_leverage(symbol, leverage)
    return {
        "leverage": leverage
    }

@app.get("/config")
async def get_config(trader_id: str):
    config = Config(trader_id=trader_id)
    return {
        "llm_config": config.llm_config,
        "exchange_config": config.exchange_config,
        "risk_config": config.risk_config,
        "system_prompt": config.system_prompt
    }

@app.post("/config")
async def set_config(
    trader_id: str,                              # Optinal
    llm_config: Optional[dict] = None,           # Optinal
    exchange_config: Optional[dict] = None,      # Optional
    risk_config: Optional[dict] = None,          # Optinal
    system_prompt: Optional[str] = None          # Optinal
):
    config = Config(trader_id=trader_id)

    if llm_config is not None:
        config.set_llm_config(llm_config)
    
    if exchange_config is not None:
        config.set_exchange_config(exchange_config)
    
    if risk_config is not None:
        config.set_risk_config(risk_config)
    
    if system_prompt is not None:
        config.set_system_prompt(system_prompt)
    
    return {
        "message": "配置更新成功",
        "trader_id": trader_id,
        "updated_fields": [
            "llm_config" if llm_config is not None else None,
            "exchange_config" if exchange_config is not None else None,
            "risk_config" if risk_config is not None else None,
            "system_prompt" if system_prompt is not None else None
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    #add swagger ui
    from fastapi.openapi.docs import get_swagger_ui_html
    @app.get("/docs")
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            url="/openapi.json",
            title="API Docs",
            swagger_favicon_url="/static/favicon.ico",
            swagger_css_url="/static/swagger-ui.css",
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_ui_init_oauth=None,
        )