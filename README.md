<div align="center">

# 🤖 LangTrader Agents

**AI 驱动的量化交易系统 | AI-Powered Quantitative Trading System**

基于 LangGraph 构建的智能加密货币交易代理，融合技术分析与大语言模型决策

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-🦜-1C3C3C?style=for-the-badge)](https://github.com/langchain-ai/langgraph)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![CCXT](https://img.shields.io/badge/CCXT-Pro-000000?style=for-the-badge)](https://github.com/ccxt/ccxt)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

<br/>

[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com/)
[![Anthropic](https://img.shields.io/badge/Anthropic-Claude-191919?style=flat-square)](https://anthropic.com/)
[![Ollama](https://img.shields.io/badge/Ollama-Local-000000?style=flat-square)](https://ollama.ai/)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)

<br/>

**⭐ 如果这个项目对你有帮助，请给一个 Star 支持！⭐**

[English](#english) | [中文](#中文)

</div>

---

## 中文

### 📖 项目简介

LangTrader Agents 是一个**模块化、可扩展**的 AI 量化交易系统。它将传统技术分析与大语言模型（LLM）的推理能力相结合，实现智能化的交易决策。

系统采用 **LangGraph StateGraph** 作为工作流引擎，支持**热插拔节点**架构，所有配置存储于 PostgreSQL 数据库，支持**零重启热更新**。

### ✨ 核心特色

<table>
<tr>
<td width="50%">

#### 🔌 热插拔插件架构
- 节点自动发现与注册
- 运行时动态加载/卸载
- 无需重启即可扩展功能

#### 🤝 多 Agent 协作
- **单 Agent 模式**：快速决策，低延迟
- **多 Agent 辩论模式**：4 角色（分析师/多头/空头/风控）辩论，提高决策质量

#### 🔧 集中配置管理
- 数据库驱动配置（PostgreSQL）
- 60 秒自动热重载
- 零硬编码，完全可配置

</td>
<td width="50%">

#### 🌐 70+ 交易所支持
- 基于 CCXT Pro 统一接口
- 支持 Hyperliquid、Binance、OKX 等
- WebSocket 实时数据流

#### 📊 量化信号引擎
- 趋势/动量/波动率/成交量 多维度分析
- 可配置权重和阈值
- 自动过滤低质量信号

#### 🛡️ 智能风控系统
- 总敞口/单币种敞口限制
- 连续亏损熔断
- 资金费率监控
- 执行失败反馈学习

</td>
</tr>
</table>

### 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      LangTrader Agents                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │ coins    │→ │ market   │→ │ quant    │→ │ debate/batch     │ │
│  │ _pick    │  │ _state   │  │ _filter  │  │ _decision        │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┬─────────┘ │
│                                                     ↓           │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     execution                             │   │
│  └──────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  Services: Trader | Market | Indicators | Performance | Cache   │
├─────────────────────────────────────────────────────────────────┤
│  LLM Factory: OpenAI | Anthropic | Ollama | DeepSeek | 智谱     │
├─────────────────────────────────────────────────────────────────┤
│  Exchange (CCXT Pro): 70+ Exchanges with WebSocket Support      │
└─────────────────────────────────────────────────────────────────┘
```

### 📦 工作流节点

| 节点 | 功能 | 特点 |
|------|------|------|
| `coins_pick` | 选币 | 按成交量/OI 动态筛选 |
| `market_state` | 市场数据 | 多时间框架 K 线 + 指标计算 |
| `quant_signal_filter` | 量化过滤 | 多维度评分，过滤噪音 |
| `batch_decision` | 批量决策 | 单 Agent 快速决策 |
| `debate_decision` | 辩论决策 | 4 Agent 多角色辩论 |
| `execution` | 执行交易 | 风控验证 + 订单执行 |

### 🚀 快速开始

> ⚠️ **前端开发中** — Web 界面即将推出，敬请期待！

目前支持命令行方式运行：

```bash
# 1. 克隆项目
git clone https://github.com/neilzhangpro/LangTrader.git
cd langtrader-agents

# 2. 安装依赖
uv sync

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库和 API 密钥

# 4. 初始化数据库
psql -d langtrader -f langtrader_pro_init.sql

# 5. 运行
uv run examples/run_once.py
```

📖 详细文档请查看 [docs/](docs/) 目录 | 📋 [更新日志](docs/CHANGELOG.md)

---

## English

### 📖 Introduction

LangTrader Agents is a **modular, extensible** AI-powered quantitative trading system. It combines traditional technical analysis with Large Language Model (LLM) reasoning capabilities for intelligent trading decisions.

The system uses **LangGraph StateGraph** as the workflow engine, supports a **hot-swappable node** architecture, with all configurations stored in PostgreSQL database, enabling **zero-restart hot updates**.

### ✨ Key Features

<table>
<tr>
<td width="50%">

#### 🔌 Hot-Swappable Plugin Architecture
- Auto-discovery and registration of nodes
- Runtime dynamic loading/unloading
- Extend functionality without restart

#### 🤝 Multi-Agent Collaboration
- **Single Agent Mode**: Fast decisions, low latency
- **Multi-Agent Debate Mode**: 4 roles (Analyst/Bull/Bear/RiskManager) debate for better decisions

#### 🔧 Centralized Configuration
- Database-driven config (PostgreSQL)
- 60-second auto hot-reload
- Zero hardcoding, fully configurable

</td>
<td width="50%">

#### 🌐 70+ Exchanges Supported
- Unified interface via CCXT Pro
- Supports Hyperliquid, Binance, OKX, etc.
- WebSocket real-time data streams

#### 📊 Quantitative Signal Engine
- Multi-dimensional analysis: Trend/Momentum/Volatility/Volume
- Configurable weights and thresholds
- Auto-filter low-quality signals

#### 🛡️ Intelligent Risk Management
- Total/single exposure limits
- Consecutive loss circuit breaker
- Funding rate monitoring
- Execution failure feedback learning

</td>
</tr>
</table>

### 🚀 Quick Start

> ⚠️ **Frontend Under Development** — Web interface coming soon!

Currently supports CLI execution:

```bash
# 1. Clone the repository
git clone https://github.com/neilzhangpro/LangTrader.git
cd langtrader-agents

# 2. Install dependencies
uv sync

# 3. Configure environment
cp .env.example .env
# Edit .env with your database and API keys

# 4. Initialize database
psql -d langtrader -f langtrader_pro_init.sql

# 5. Run
uv run examples/run_once.py
```

📖 See [docs/](docs/) for detailed documentation | 📋 [Changelog](docs/CHANGELOG.md)

---

<div align="center">

## ⭐ Star History

如果这个项目对你有帮助，请给我们一个 Star！

If you find this project helpful, please give us a Star!

[![Star History Chart](https://api.star-history.com/svg?repos=neilzhangpro/LangTrader&type=Date)](https://star-history.com/#neilzhangpro/LangTrader&Date)

---

### 🙏 致谢 | Acknowledgements

[![LangGraph](https://img.shields.io/badge/LangGraph-Workflow-1C3C3C?style=flat-square)](https://github.com/langchain-ai/langgraph)
[![CCXT](https://img.shields.io/badge/CCXT-Exchange-000000?style=flat-square)](https://github.com/ccxt/ccxt)
[![LangChain](https://img.shields.io/badge/LangChain-LLM-1C3C3C?style=flat-square)](https://github.com/langchain-ai/langchain)
[![pandas-ta](https://img.shields.io/badge/pandas--ta-Indicators-150458?style=flat-square)](https://github.com/twopirllc/pandas-ta)

---

### ⚠️ 免责声明 | Disclaimer

本软件仅供教育和研究目的。加密货币交易涉及重大损失风险。作者不对使用本软件造成的任何财务损失负责。

This software is for educational and research purposes only. Cryptocurrency trading involves significant risk of loss. The authors are not responsible for any financial losses incurred through the use of this software.

---

**MIT License** | Copyright © 2024-2026

</div>
