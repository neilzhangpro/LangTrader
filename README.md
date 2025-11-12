# LangTrader 🤖

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-1.0+-1C3C3C?style=flat&logo=langchain)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0+-green?style=flat)](https://langchain-ai.github.io/langgraph/)
[![Hyperliquid](https://img.shields.io/badge/Hyperliquid-SDK-orange?style=flat)](https://hyperliquid.xyz/)
[![Loguru](https://img.shields.io/badge/Logging-Loguru-blue?style=flat)](https://github.com/Delgan/loguru)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![uv](https://img.shields.io/badge/uv-managed-blue?style=flat)](https://github.com/astral-sh/uv)

AI-powered cryptocurrency trading bot using LangChain and Hyperliquid DEX.

**Official X: @AIBTCAI** [@AIBTCAI](https://x.com/AIBTCAI)


## Powerful AI trade bot driven by LangGraph 🚀
LangTrader is a powerful, open-source AI-driven cryptocurrency trading bot built on top of [LangChain](https://www.langchain.com/), [LangGraph](https://langchain-ai.github.io/langgraph/), and the decentralized exchange [Hyperliquid](https://hyperliquid.xyz/). Leveraging the latest advancements in Python, AI, and on-chain trading, LangTrader automates trading decisions with sophisticated technical indicator analysis, advanced logging via Loguru, and seamless DEX integration.

**Key Features:**
- **Automated Trading**: Executes trades automatically based on real-time technical indicator signals (e.g., RSI, MACD, Bollinger Bands, SMA/EMA) and AI-driven insights.
- **AI Integration**: Utilizes the LangChain ecosystem and LangGraph for sophisticated decision-making workflows.
- **Hyperliquid DEX Support**: Place and manage orders, leverage positions, and handle risk on the Hyperliquid decentralized exchange.
- **Detailed Logging**: All actions and decisions are logged using Loguru for transparency and easy debugging.
- **Database Integration**: Stores trading decisions, positions, and performance metrics in a PostgreSQL database for analysis and backtesting.
- **Position Management**: Tracks open positions, calculates realized/unrealized PnL, and manages stop-loss/take-profit levels.
- **Risk Management**: Implements configurable risk controls including maximum leverage, stop-loss percentages, and position sizing.
- **Historical Performance Analysis**: Analyzes past trading performance to inform future decisions.
- **Customizable & Extensible**: Modular architecture makes it easy to add strategies, indicators, or integrate with other AI services.

**Getting Started:**  
View [main.py](main.py) for an example of how to use LangTrader. Simply configure your environment and run the bot to begin automated trading.

**Disclaimer:**  
This project is for educational purposes and not financial advice. Use at your own risk.

## Progress
- 05/11/2025: Finish basic structure of project, fetch marketing info & simply analyze trade signal & place order & cancel order
- 06/11/2025: Restructure project & add unit testing & init database, Now you can run `uv run pytest`
- 06/11/2025: Add FastAPI & database
- 10/11/2025: Add LangGraph & finish main parts
- 12/11/2025: Implement position tracking, PnL calculation, and database storage for trading decisions and positions
- 12/11/2025: Add trend-following logic to prevent unnecessary closing of positions when trend continues

## To-Do List
- [ ] Implement more sophisticated trading strategies
- [ ] Add backtesting capabilities
- [ ] Implement advanced risk management features
- [ ] Add support for multiple trading pairs
- [ ] Improve error handling and recovery mechanisms
- [ ] Add more comprehensive logging and monitoring
- [ ] Implement position sizing based on volatility

