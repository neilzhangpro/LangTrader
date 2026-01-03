"""
API Documentation Endpoints
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/docs-page", tags=["Documentation"])

# =============================================================================
# Documentation HTML Page
# =============================================================================

DOCS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LangTrader API Documentation</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-tertiary: #21262d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent: #58a6ff;
            --accent-green: #3fb950;
            --accent-orange: #d29922;
            --accent-red: #f85149;
            --border: #30363d;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        header {
            border-bottom: 1px solid var(--border);
            padding-bottom: 2rem;
            margin-bottom: 2rem;
        }
        
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--accent), var(--accent-green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .subtitle {
            color: var(--text-secondary);
            font-size: 1.2rem;
        }
        
        .nav-links {
            display: flex;
            gap: 1rem;
            margin-top: 1.5rem;
        }
        
        .nav-links a {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.75rem 1.5rem;
            background: var(--bg-secondary);
            color: var(--accent);
            text-decoration: none;
            border-radius: 8px;
            border: 1px solid var(--border);
            transition: all 0.2s;
        }
        
        .nav-links a:hover {
            background: var(--bg-tertiary);
            border-color: var(--accent);
        }
        
        h2 {
            color: var(--text-primary);
            margin: 2rem 0 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid var(--border);
        }
        
        h3 {
            color: var(--accent);
            margin: 1.5rem 0 0.75rem;
        }
        
        .endpoint-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
        }
        
        .endpoint-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }
        
        .method {
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.875rem;
        }
        
        .method-get { background: #1f6feb; color: white; }
        .method-post { background: var(--accent-green); color: white; }
        .method-patch { background: var(--accent-orange); color: white; }
        .method-delete { background: var(--accent-red); color: white; }
        .method-ws { background: #a371f7; color: white; }
        
        .endpoint-path {
            font-family: 'Monaco', 'Menlo', monospace;
            color: var(--text-primary);
        }
        
        .endpoint-desc {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        code {
            background: var(--bg-tertiary);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 0.875rem;
        }
        
        pre {
            background: var(--bg-tertiary);
            padding: 1rem;
            border-radius: 8px;
            overflow-x: auto;
            margin: 1rem 0;
        }
        
        pre code {
            background: none;
            padding: 0;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }
        
        .feature-card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.5rem;
        }
        
        .feature-card h4 {
            color: var(--accent);
            margin-bottom: 0.5rem;
        }
        
        .feature-card p {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        footer {
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-secondary);
        }
        
        footer a {
            color: var(--accent);
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>LangTrader API</h1>
            <p class="subtitle">AI-Powered Cryptocurrency Trading System</p>
            <div class="nav-links">
                <a href="/api/docs">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                    Swagger UI
                </a>
                <a href="/api/redoc">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z"/>
                    </svg>
                    ReDoc
                </a>
                <a href="/api/openapi.json">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5"/>
                    </svg>
                    OpenAPI JSON
                </a>
            </div>
        </header>
        
        <section>
            <h2>Quick Start</h2>
            <div class="grid">
                <div class="feature-card">
                    <h4>1. Get API Key</h4>
                    <p>Use the default dev key: <code>dev-key-123</code> or configure your own in <code>.env</code></p>
                </div>
                <div class="feature-card">
                    <h4>2. Test Connection</h4>
                    <p>Check the health endpoint: <code>GET /api/v1/health</code></p>
                </div>
                <div class="feature-card">
                    <h4>3. List Bots</h4>
                    <p>Get all bots: <code>GET /api/v1/bots</code> with <code>X-API-Key</code> header</p>
                </div>
                <div class="feature-card">
                    <h4>4. Start Trading</h4>
                    <p>Start a bot: <code>POST /api/v1/bots/{id}/start</code></p>
                </div>
            </div>
        </section>
        
        <section>
            <h2>Authentication</h2>
            <p>All endpoints except <code>/api/v1/health</code> require an API Key:</p>
            <pre><code>curl -H "X-API-Key: dev-key-123" http://localhost:8000/api/v1/bots</code></pre>
        </section>
        
        <section>
            <h2>REST Endpoints</h2>
            
            <h3>Health & Auth</h3>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/api/v1/health</span>
                </div>
                <p class="endpoint-desc">Health check - no authentication required</p>
            </div>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/api/v1/auth/validate</span>
                </div>
                <p class="endpoint-desc">Validate API key</p>
            </div>
            
            <h3>Bot Management</h3>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/api/v1/bots</span>
                </div>
                <p class="endpoint-desc">List all bots with pagination</p>
            </div>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/api/v1/bots</span>
                </div>
                <p class="endpoint-desc">Create a new bot</p>
            </div>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/api/v1/bots/{id}</span>
                </div>
                <p class="endpoint-desc">Get bot details</p>
            </div>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-patch">PATCH</span>
                    <span class="endpoint-path">/api/v1/bots/{id}</span>
                </div>
                <p class="endpoint-desc">Update bot configuration</p>
            </div>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/api/v1/bots/{id}/start</span>
                </div>
                <p class="endpoint-desc">Start trading bot</p>
            </div>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/api/v1/bots/{id}/stop</span>
                </div>
                <p class="endpoint-desc">Stop trading bot</p>
            </div>
            
            <h3>Trades & Performance</h3>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/api/v1/trades</span>
                </div>
                <p class="endpoint-desc">List trade history</p>
            </div>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/api/v1/performance/{bot_id}</span>
                </div>
                <p class="endpoint-desc">Get performance metrics (Sharpe, win rate, drawdown)</p>
            </div>
            
            <h3>Backtesting</h3>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-post">POST</span>
                    <span class="endpoint-path">/api/v1/backtests</span>
                </div>
                <p class="endpoint-desc">Start a backtest</p>
            </div>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-get">GET</span>
                    <span class="endpoint-path">/api/v1/backtests/{task_id}</span>
                </div>
                <p class="endpoint-desc">Get backtest status and results</p>
            </div>
        </section>
        
        <section>
            <h2>WebSocket</h2>
            <div class="endpoint-card">
                <div class="endpoint-header">
                    <span class="method method-ws">WS</span>
                    <span class="endpoint-path">/ws/trading/{bot_id}?api_key=xxx</span>
                </div>
                <p class="endpoint-desc">Real-time trading updates (status, trades, decisions)</p>
            </div>
            
            <h3>Example Usage</h3>
            <pre><code>const ws = new WebSocket('ws://localhost:8000/ws/trading/1?api_key=dev-key-123');

ws.onopen = () => console.log('Connected');

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    console.log(msg.event, msg.data);
};

// Subscribe to additional channel
ws.send(JSON.stringify({
    action: 'subscribe',
    channel: 'system:alerts'
}));</code></pre>
        </section>
        
        <footer>
            <p>LangTrader API v1.0.0 | 
            <a href="https://github.com/neilzhangpro/LangTrader">GitHub</a> | 
            Built with FastAPI</p>
        </footer>
    </div>
</body>
</html>
"""


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def docs_page():
    """
    API Documentation Page
    
    Returns a styled HTML documentation page with endpoint overview.
    """
    return HTMLResponse(content=DOCS_HTML)


@router.get("/endpoints", tags=["Documentation"])
async def list_endpoints():
    """
    List all API endpoints with descriptions
    """
    return {
        "rest": {
            "health": {
                "GET /api/v1/health": "Health check (no auth)",
                "GET /api/v1/health/ready": "Kubernetes readiness probe",
                "GET /api/v1/health/live": "Kubernetes liveness probe",
            },
            "auth": {
                "GET /api/v1/auth/validate": "Validate API key",
                "GET /api/v1/auth/info": "Get auth info",
            },
            "bots": {
                "GET /api/v1/bots": "List all bots",
                "POST /api/v1/bots": "Create bot",
                "GET /api/v1/bots/{id}": "Get bot details",
                "PATCH /api/v1/bots/{id}": "Update bot",
                "DELETE /api/v1/bots/{id}": "Delete bot (soft)",
                "GET /api/v1/bots/{id}/status": "Get bot status",
                "POST /api/v1/bots/{id}/start": "Start bot",
                "POST /api/v1/bots/{id}/stop": "Stop bot",
                "POST /api/v1/bots/{id}/restart": "Restart bot",
            },
            "trades": {
                "GET /api/v1/trades": "List trades",
                "GET /api/v1/trades/{id}": "Get trade details",
                "GET /api/v1/trades/summary": "Get trade summary",
                "GET /api/v1/trades/daily": "Get daily performance",
            },
            "performance": {
                "GET /api/v1/performance/{bot_id}": "Get performance metrics",
                "GET /api/v1/performance/{bot_id}/recent": "Get recent trades summary",
                "GET /api/v1/performance/compare": "Compare bots",
            },
            "backtests": {
                "POST /api/v1/backtests": "Start backtest",
                "GET /api/v1/backtests": "List backtests",
                "GET /api/v1/backtests/{task_id}": "Get backtest status",
                "DELETE /api/v1/backtests/{task_id}": "Cancel backtest",
            },
            "workflows": {
                "GET /api/v1/workflows": "List workflows",
                "GET /api/v1/workflows/{id}": "Get workflow details",
                "GET /api/v1/workflows/{id}/nodes": "Get workflow nodes",
                "GET /api/v1/workflows/plugins": "List available plugins",
            },
        },
        "websocket": {
            "WS /ws/trading/{bot_id}": "Real-time trading updates",
            "WS /ws/system": "System-wide alerts",
        },
        "channels": [
            "bot:{id}:status",
            "bot:{id}:trades",
            "bot:{id}:decisions",
            "bot:{id}:cycles",
            "system:alerts",
        ],
    }

