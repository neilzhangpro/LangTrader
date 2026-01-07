"""
LangTrader API - FastAPI Application Entry Point

安全特性：
- API Key 认证
- 速率限制（防止滥用）
- 加密存储敏感信息
- WebSocket 安全认证
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from langtrader_api.config import settings
from langtrader_api.dependencies import init_services, shutdown_services
from langtrader_api.routes.v1 import router as v1_router
from langtrader_api.websocket.handlers import router as ws_router
from langtrader_api.middleware.error_handler import setup_exception_handlers
from langtrader_api.middleware.rate_limiter import limiter, rate_limit_exceeded_handler
from langtrader_api.services.bot_manager import bot_manager


# =============================================================================
# OpenAPI Tags Metadata
# =============================================================================

tags_metadata = [
    {
        "name": "Health",
        "description": "Health check endpoints for monitoring and Kubernetes probes.",
    },
    {
        "name": "Authentication",
        "description": "API Key validation and authentication info.",
    },
    {
        "name": "Bots",
        "description": "Trading bot management - create, configure, start/stop bots, positions and balance.",
    },
    {
        "name": "Trades",
        "description": "Trade history and transaction records.",
    },
    {
        "name": "Performance",
        "description": "Performance metrics and analytics - win rate, Sharpe ratio, drawdown.",
    },
    {
        "name": "Backtests",
        "description": "Run and manage backtests on historical data.",
    },
    {
        "name": "Workflows",
        "description": "Workflow and plugin management.",
    },
    {
        "name": "Exchanges",
        "description": "Exchange configuration management - API keys, connection testing, balance.",
    },
    {
        "name": "LLM Configs",
        "description": "LLM configuration management - OpenAI, Anthropic, custom providers.",
    },
    {
        "name": "Dashboard",
        "description": "Dashboard aggregation APIs - overview, charts data, statistics.",
    },
    {
        "name": "WebSocket",
        "description": "Real-time updates via WebSocket connections.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    # Startup
    await init_services()
    yield
    # Shutdown
    await bot_manager.stop_all()
    await shutdown_services()


# =============================================================================
# FastAPI Application
# =============================================================================

API_DESCRIPTION = """
# LangTrader API

AI-Powered Cryptocurrency Trading System API built with FastAPI.

## Overview

LangTrader is an intelligent trading system that combines:
- **Quantitative Analysis** - Technical indicators and signal scoring
- **AI Decision Making** - LLM-powered trading decisions
- **Risk Management** - Dynamic position sizing and risk limits
- **Backtesting** - Test strategies on historical data

## Authentication

All endpoints (except `/api/v1/health`) require an API Key in the header:

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/bots
```

## Quick Start

### 1. List available bots
```bash
GET /api/v1/bots
```

### 2. Start a bot
```bash
POST /api/v1/bots/{bot_id}/start
```

### 3. Monitor via WebSocket (Secure Method)
```javascript
// 推荐方式：连接后发送认证消息
const ws = new WebSocket('ws://localhost:8000/ws/trading/1');
ws.onopen = () => {
    ws.send(JSON.stringify({action: "auth", api_key: "your-key"}));
};
ws.onmessage = (event) => console.log(JSON.parse(event.data));
```

### 4. View performance
```bash
GET /api/v1/performance/{bot_id}
```

## Response Format

All responses follow a standard format:

```json
{
  "success": true,
  "data": { ... },
  "message": "Optional message",
  "timestamp": "2024-01-01T00:00:00"
}
```

## Error Handling

Errors return appropriate HTTP status codes with details:

```json
{
  "success": false,
  "error": "Not Found",
  "detail": "Bot with id 999 not found",
  "code": "HTTP_404",
  "timestamp": "2024-01-01T00:00:00"
}
```

## Rate Limiting

API requests are rate limited to prevent abuse:
- **Default**: 120 requests/minute per API key
- **Authentication**: 10 requests/minute (brute-force protection)
- **Trading operations**: 30 requests/minute
- **Backtests**: 5 requests/minute

Exceeding the limit returns HTTP 429 with `Retry-After` header.

## WebSocket Channels

Subscribe to real-time updates:
- `bot:{id}:status` - Bot status changes
- `bot:{id}:trades` - Trade executions
- `bot:{id}:decisions` - AI decisions
- `system:alerts` - System-wide alerts

---

For more information, visit the [GitHub Repository](https://github.com/neilzhangpro/LangTrader).
"""

app = FastAPI(
    title=settings.APP_NAME,
    description=API_DESCRIPTION,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=tags_metadata,
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    contact={
        "name": "LangTrader Team",
        "url": "https://github.com/neilzhangpro/LangTrader",
    },
    lifespan=lifespan,
)

# =============================================================================
# Rate Limiting
# =============================================================================

# 注册限流器到 app
app.state.limiter = limiter

# 注册速率限制异常处理
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# =============================================================================
# Middleware
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type", "Authorization"],
)

# Setup exception handlers
setup_exception_handlers(app)

# =============================================================================
# Routes
# =============================================================================

app.include_router(v1_router, prefix="/api/v1")
app.include_router(ws_router, prefix="/ws")


# =============================================================================
# Root Endpoint
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - returns API information"""
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "docs": "/api/docs",
        "health": "/api/v1/health",
        "rate_limit": f"{settings.RATE_LIMIT_PER_MINUTE}/minute",
    }


# =============================================================================
# CLI Entry Point
# =============================================================================

def run_server():
    """Run the API server (for CLI usage)"""
    import uvicorn
    uvicorn.run(
        "langtrader_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    run_server()
