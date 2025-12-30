# LangTrader Agents

An AI-powered cryptocurrency trading system built with LangGraph, combining quantitative analysis with Large Language Model decision-making.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

LangTrader Agents is a modular, plugin-based trading system that leverages AI to make informed trading decisions. The system integrates technical analysis, quantitative signals, and LLM reasoning to execute trades on cryptocurrency exchanges.

### Key Features

- **AI-Driven Decisions** — Uses LLMs (OpenAI, Anthropic, Ollama) to analyse market conditions
- **Quantitative Signal Filtering** — Pre-filters trading opportunities using technical indicators
- **Dynamic Risk Management** — Configurable risk limits and position sizing
- **Plugin Architecture** — Hot-swappable workflow nodes stored in database
- **Backtesting Engine** — Test strategies on historical data without exchange connection
- **Real-time Data** — WebSocket streams for live market data via CCXT Pro
- **State Checkpointing** — LangGraph checkpoints for workflow recovery

---

## System Architecture

```mermaid
flowchart TB
    subgraph External [External Services]
        EX[Cryptocurrency Exchange]
        LLM[LLM Provider]
        DB[(PostgreSQL)]
    end
    
    subgraph Core [LangTrader Core]
        subgraph Services [Services Layer]
            TR[Trader Service]
            SM[Stream Manager]
            MK[Market Service]
            PS[Performance Service]
            CA[Cache]
            RL[Rate Limiter]
        end
        
        subgraph Workflow [LangGraph Workflow]
            CP[Coins Pick]
            MS[Market State]
            QF[Quant Filter]
            MA[Market Analyzer]
            DE[Decision]
            RM[Risk Monitor]
            EXE[Execution]
        end
        
        subgraph Plugins [Plugin System]
            REG[Plugin Registry]
            CTX[Plugin Context]
            WB[Workflow Builder]
        end
    end
    
    EX <-->|CCXT Pro| TR
    EX <-->|WebSocket| SM
    LLM <-->|API| MA
    LLM <-->|API| DE
    DB <-->|SQLModel| WB
    DB <-->|SQLModel| PS
    
    TR --> MK
    SM --> MK
    MK --> Workflow
    
    REG --> WB
    CTX --> Workflow
    WB --> Workflow
    
    CP --> MS --> QF --> MA --> DE --> RM --> EXE
```

---

## Trading Workflow

The trading cycle follows a defined sequence of nodes, each responsible for a specific task:

```mermaid
sequenceDiagram
    participant User
    participant System as Trading System
    participant Exchange
    participant LLM as AI Model
    
    User->>System: Start Bot
    
    loop Every Cycle (3min default)
        System->>Exchange: Fetch Market Data
        Exchange-->>System: OHLCV, Funding Rates
        
        System->>System: 1. Select Coins (Open Interest)
        System->>System: 2. Fetch Market State
        System->>System: 3. Calculate Indicators
        System->>System: 4. Quantitative Filter
        
        System->>LLM: 5. Market Analysis Prompt
        LLM-->>System: Market Insights
        
        System->>LLM: 6. Decision Prompt
        LLM-->>System: Trade Decision (JSON)
        
        System->>System: 7. Risk Validation
        
        alt Decision Approved
            System->>Exchange: 8. Execute Trade
            Exchange-->>System: Order Result
        else Decision Rejected
            System->>System: Log & Skip
        end
        
        System->>System: Update State & Checkpoint
    end
```

---

## Data Flow (Swimlane)

```mermaid
flowchart LR
    subgraph Exchange [Exchange Layer]
        E1[REST API]
        E2[WebSocket]
    end
    
    subgraph Data [Data Collection]
        D1[OHLCV 3m/4h]
        D2[Funding Rates]
        D3[Open Interest]
        D4[Account Balance]
    end
    
    subgraph Analysis [Analysis Layer]
        A1[Technical Indicators]
        A2[Quant Signals]
        A3[Performance Metrics]
    end
    
    subgraph AI [AI Layer]
        AI1[Market Analyzer]
        AI2[Decision Engine]
    end
    
    subgraph Execution [Execution Layer]
        X1[Risk Monitor]
        X2[Order Executor]
        X3[Trade Recorder]
    end
    
    E1 --> D1
    E1 --> D2
    E1 --> D3
    E1 --> D4
    E2 --> D1
    
    D1 --> A1
    D2 --> A2
    D3 --> A1
    A1 --> A2
    
    A2 --> AI1
    A3 --> AI2
    AI1 --> AI2
    
    AI2 --> X1
    X1 --> X2
    X2 --> X3
    X3 --> A3
```

---

## Project Structure

```
LangTrader_Agents/
├── packages/
│   └── langtrader_core/
│       ├── backtest/           # Backtesting engine
│       │   ├── engine.py
│       │   ├── mock_trader.py
│       │   └── mock_performance.py
│       ├── data/               # Database models & repositories
│       │   ├── models/
│       │   └── repositories/
│       ├── graph/              # LangGraph workflow
│       │   ├── nodes/          # Workflow nodes
│       │   └── state.py        # State definitions
│       ├── plugins/            # Plugin system
│       │   ├── protocol.py
│       │   ├── registry.py
│       │   └── workflow.py
│       ├── services/           # Core services
│       │   ├── trader.py
│       │   ├── market.py
│       │   ├── indicators.py
│       │   └── ...
│       └── prompts/            # LLM prompt templates
├── examples/
│   ├── run_once.py             # Single bot runner
│   ├── run_backtest.py         # Backtest runner
│   └── multi_bot_runner.py     # Multiple bots
├── tests/                      # Unit tests
├── scripts/                    # Database migrations
├── configs/                    # Configuration files
└── docs/                       # Documentation
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Exchange API credentials (Hyperliquid, Binance, etc.)
- LLM API key (OpenAI, Anthropic, or local Ollama)

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/your-org/langtrader-agents.git
cd langtrader-agents
```

2. **Install dependencies using uv**

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install
uv sync
```

3. **Set up environment variables**

```bash
cp .env.example .env

# Edit .env with your credentials
DATABASE_URL=postgresql://user:pass@localhost:5432/langtrader
OPENAI_API_KEY=sk-...
LANGSMITH_API_KEY=...  # Optional, for tracing
```

4. **Initialise the database**

```bash
psql -d langtrader -f langtrader_pro_init.sql
```

5. **Configure your bot**

The bot configuration is stored in the `bots` table. Key settings include:
- Exchange credentials
- LLM model selection
- Risk parameters
- Quantitative signal weights

---

## Usage

### Running Live Trading

```bash
# Run a single trading bot
uv run examples/run_once.py

# Run multiple bots
uv run examples/multi_bot_runner.py
```

### Running Backtests

```bash
# Run backtest with default settings
uv run examples/run_backtest.py

# Backtest will use historical data from exchange
# Results are printed to console
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_mock_trader.py -v
```

---

## Configuration

### Bot Configuration (Database)

| Field | Description | Default |
|-------|-------------|---------|
| `trading_mode` | `paper` or `live` | `paper` |
| `max_concurrent_symbols` | Maximum coins to trade | 5 |
| `cycle_interval_seconds` | Time between cycles | 180 |
| `max_leverage` | Maximum leverage | 5 |
| `max_position_size_percent` | Max position as % of balance | 10% |

### Quantitative Signal Weights

```json
{
  "trend": 0.4,
  "momentum": 0.3,
  "volume": 0.2,
  "sentiment": 0.1
}
```

### Risk Limits

```json
{
  "max_total_exposure_pct": 0.8,
  "max_consecutive_losses": 5,
  "max_single_symbol_pct": 0.3
}
```

---

## Workflow Nodes

| Node | Purpose | Requires |
|------|---------|----------|
| `coins_pick` | Select trading coins based on volume/OI | Exchange |
| `market_state` | Fetch OHLCV and calculate indicators | Exchange |
| `quant_signal_filter` | Filter coins by quantitative score | - |
| `market_analyzer` | AI analysis of market conditions | LLM |
| `decision` | AI trading decision | LLM |
| `risk_monitor` | Validate risk limits | - |
| `execution` | Execute trades | Exchange |

---

## Extending the System

### Creating a Custom Node

```python
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import State

class MyCustomNode(NodePlugin):
    metadata = NodeMetadata(
        name="my_custom_node",
        display_name="My Custom Node",
        version="1.0.0",
        author="Your Name",
        description="Does something useful",
        category="analysis",
        insert_after="market_state",
        suggested_order=2.5,
    )
    
    async def run(self, state: State) -> State:
        # Your logic here
        return state
```

Nodes are automatically discovered and registered when placed in `packages/langtrader_core/graph/nodes/`.

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `Exchange not found` | Check exchange credentials in database |
| `No markets loaded` | Ensure exchange supports CCXT Pro |
| `LLM timeout` | Increase timeout or check API key |
| `Checkpoint error` | Verify PostgreSQL connection |

### Logs

Logs are stored in `logs/langtrader.log`. Enable debug logging by setting:

```python
logger = get_logger("module_name", level="DEBUG")
```

---

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## Disclaimer

This software is provided for educational and research purposes only. Cryptocurrency trading involves significant risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.

---

## Licence

This project is licensed under the MIT Licence - see the [LICENCE](LICENCE) file for details.

---

## Acknowledgements

- [LangGraph](https://github.com/langchain-ai/langgraph) — Workflow orchestration
- [CCXT](https://github.com/ccxt/ccxt) — Exchange connectivity
- [LangChain](https://github.com/langchain-ai/langchain) — LLM integration
- [pandas-ta](https://github.com/twopirllc/pandas-ta) — Technical analysis

