# LangTrader API Server
from fastapi import FastAPI, Depends, HTTPException, Security, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from src.LangTrader.config import Config
from src.LangTrader.db import Database
from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from src.LangTrader.market import CryptoFetcher
from src.LangTrader.backtest.backtest_runner import BacktestRunner
from src.LangTrader.ai.historical_performance import HistoricalPerformance
from src.LangTrader.ai.performance_tracker import RealTimePerformanceTracker
from src.LangTrader.utils import logger
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta
import pandas as pd
import json
import os

# ===== Pydantic Models =====

class BacktestRequest(BaseModel):
    trader_id: str
    start_date: str = "2024-01-01"
    end_date: str = "2024-11-01"
    initial_balance: float = 10000.0
    symbols: Optional[List[str]] = None
    strategies: Optional[List[str]] = None
    custom_prompt: Optional[str] = None

class CreateTraderRequest(BaseModel):
    name: str
    symbols: List[str]
    llm_config: dict
    exchange_config: dict
    risk_config: dict
    system_prompt: str

class UpdateTraderConfigRequest(BaseModel):
    llm_config: Optional[dict] = None
    exchange_config: Optional[dict] = None
    risk_config: Optional[dict] = None
    symbols: Optional[List[str]] = None

class UpdatePromptsRequest(BaseModel):
    custom_system_prompt: Optional[str] = None
    custom_user_prompt: Optional[str] = None

class HyperliquidConfigRequest(BaseModel):
    secret_key: str
    account_address: str

# ===== 辅助函数 =====

def read_hyperliquid_config():
    """读取config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"读取config.json失败: {e}")
        return None

def write_hyperliquid_config(secret_key: str, account_address: str):
    """写入config.json"""
    try:
        config = {
            "secret_key": secret_key,
            "account_address": account_address
        }
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"写入config.json失败: {e}")
        return False

def validate_ethereum_address(address: str) -> bool:
    """验证以太坊地址格式"""
    if not address:
        return False
    if not address.startswith('0x'):
        return False
    if len(address) != 42:
        return False
    try:
        int(address[2:], 16)  # 验证是否为有效十六进制
        return True
    except ValueError:
        return False

def validate_private_key(key: str) -> bool:
    """验证私钥格式"""
    if not key:
        return False
    if not key.startswith('0x'):
        return False
    if len(key) != 66:
        return False
    try:
        int(key[2:], 16)  # 验证是否为有效十六进制
        return True
    except ValueError:
        return False

# ===== FastAPI App =====

app = FastAPI(title="LangTrader API", version="1.0.0")

# CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局Database实例
db = Database()

# API认证
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """验证API token"""
    token = credentials.credentials
    valid_token = os.getenv("API_TOKEN")
    
    if token != valid_token:
        raise HTTPException(
            status_code=403,
            detail="Invalid authentication token"
        )
    return token

# ===== 系统健康 =====

@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/")
def read_root():
    """根路径"""
    return {
        "message": "LangTrader API Server",
        "version": "1.0.0",
        "docs": "/docs"
    }

# ===== Phase 1: 核心监控API =====

@app.get("/api/account")
async def get_account(trader_id: str = Query(..., description="Trader ID")):
    """获取账户信息"""
    try:
        config = Config(trader_id=trader_id)
        hyperliquid = hyperliquidAPI()
        balance = hyperliquid.get_account_balance()
        
        if not balance:
            raise HTTPException(status_code=500, detail="无法获取账户信息")
        
        margin_summary = balance.get('marginSummary', {})
        
        return {
            "trader_id": trader_id,
            "equity": float(margin_summary.get('accountValue', 0)),
            "withdrawable": float(balance.get('withdrawable', 0)),
            "margin_used": float(margin_summary.get('totalMarginUsed', 0)),
            "open_positions": len(balance.get('assetPositions', [])),
            "total_position_value": float(margin_summary.get('totalNtlPos', 0))
        }
    except Exception as e:
        logger.error(f"获取账户信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'config' in locals():
            config.close()

@app.get("/api/positions")
async def get_positions(trader_id: str = Query(...)):
    """获取持仓列表"""
    try:
        hyperliquid = hyperliquidAPI()
        balance = hyperliquid.get_account_balance()
        
        if not balance:
            return {"positions": []}
        
        positions = []
        for asset in balance.get('assetPositions', []):
            pos = asset.get('position', {})
            size = float(pos.get('szi', 0))
            
            if size == 0:
                continue
            
            positions.append({
                "symbol": pos.get('coin'),
                "side": "long" if size > 0 else "short",
                "size": abs(size),
                "entry_price": float(pos.get('entryPx', 0)),
                "position_value": float(pos.get('positionValue', 0)),
                "unrealized_pnl": float(pos.get('unrealizedPnl', 0)),
                "leverage": pos.get('leverage', {}).get('value', 1),
                "margin_used": float(pos.get('marginUsed', 0))
            })
        
        return {"positions": positions}
    except Exception as e:
        logger.error(f"获取持仓列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/decisions/latest")
async def get_latest_decisions(
    trader_id: str = Query(...),
    limit: int = Query(5, ge=1, le=50)
):
    """获取最新决策"""
    try:
        decisions = db.execute("""
            SELECT id, symbol, action, confidence, 
                   llm_analysis, created_at, winner_model,
                   competition_id, risk_passed, executed
            FROM decisions
            WHERE trader_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (trader_id, limit))
        
        # 转换数据类型
        result = []
        for d in decisions:
            result.append({
                "id": str(d['id']),
                "symbol": d['symbol'],
                "action": d['action'],
                "confidence": float(d['confidence']) if d['confidence'] else 0.0,
                "analysis": d['llm_analysis'],
                "created_at": d['created_at'].isoformat(),
                "winner_model": d['winner_model'],
                "competition_id": str(d['competition_id']) if d['competition_id'] else None,
                "risk_passed": d['risk_passed'],
                "executed": d['executed']
            })
        
        return {"decisions": result}
    except Exception as e:
        logger.error(f"获取最新决策失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/statistics")
async def get_statistics(trader_id: str = Query(...)):
    """获取统计信息"""
    try:
        # 决策统计
        decision_stats = db.execute("""
            SELECT 
                COUNT(*) as total_decisions,
                COUNT(CASE WHEN executed THEN 1 END) as executed_count
            FROM decisions
            WHERE trader_id = %s
        """, (trader_id,))
        
        # 交易统计
        position_stats = db.execute("""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as winning,
                COUNT(CASE WHEN realized_pnl < 0 THEN 1 END) as losing,
                COALESCE(SUM(realized_pnl), 0) as total_pnl,
                COALESCE(AVG(CASE WHEN realized_pnl > 0 THEN realized_pnl END), 0) as avg_win,
                COALESCE(AVG(CASE WHEN realized_pnl < 0 THEN realized_pnl END), 0) as avg_loss
            FROM positions
            WHERE trader_id = %s AND status = 'closed'
        """, (trader_id,))
        
        ds = decision_stats[0] if decision_stats else {}
        ps = position_stats[0] if position_stats else {}
        
        total_trades = ps.get('total_trades', 0)
        winning = ps.get('winning', 0)
        win_rate = winning / total_trades if total_trades > 0 else 0
        
        return {
            "total_decisions": ds.get('total_decisions', 0),
            "executed_count": ds.get('executed_count', 0),
            "total_trades": total_trades,
            "winning_trades": winning,
            "losing_trades": ps.get('losing', 0),
            "win_rate": float(win_rate),
            "total_pnl": float(ps.get('total_pnl', 0)),
            "avg_win": float(ps.get('avg_win', 0)),
            "avg_loss": float(ps.get('avg_loss', 0))
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/equity-history")
async def get_equity_history(
    trader_id: str = Query(...),
    days: int = Query(7, ge=1, le=365)
):
    """获取权益历史（图表数据）"""
    try:
        start_time = datetime.now() - timedelta(days=days)
        
        history = db.execute("""
            SELECT timestamp, equity, open_positions
            FROM equity_history
            WHERE trader_id = %s
            AND timestamp >= %s
            ORDER BY timestamp
        """, (trader_id, start_time))
        
        return {
            "data": [
                {
                    "time": h['timestamp'].isoformat(),
                    "equity": float(h['equity']),
                    "open_positions": h['open_positions']
                }
                for h in history
            ]
        }
    except Exception as e:
        logger.error(f"获取权益历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/performance")
async def get_performance(trader_id: str = Query(...)):
    """获取AI学习表现分析"""
    try:
        config = Config(trader_id=trader_id)
        hist_perf = HistoricalPerformance(config)
        perf_tracker = RealTimePerformanceTracker(trader_id, db)
        
        # 币种表现
        coin_perf = hist_perf.get_coin_performance_analysis(trader_id)
        
        # 失败/成功模式
        loss_patterns = hist_perf.analyze_recent_losses(trader_id)
        win_patterns = hist_perf.analyze_recent_wins(trader_id)
        
        # 实时性能
        real_time = perf_tracker.calculate_real_time_metrics(lookback_days=30)
        
        # 交易频率检查
        freq_check = hist_perf.check_trading_frequency(trader_id)
        
        # 连续止损检查
        sl_check = hist_perf.check_consecutive_stop_loss(trader_id)
        
        return {
            "coin_performance": coin_perf,
            "failure_patterns": loss_patterns,
            "success_patterns": win_patterns,
            "real_time_metrics": real_time,
            "frequency_check": freq_check,
            "stop_loss_check": sl_check
        }
    except Exception as e:
        logger.error(f"获取AI学习表现失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'config' in locals():
            config.close()

# ===== Phase 2: 配置管理API =====

@app.get("/api/traders/{trader_id}/config")
async def get_trader_config(trader_id: str):
    """获取trader配置"""
    try:
        config = Config(trader_id=trader_id)
        
        return {
            "trader_id": trader_id,
            "symbols": config.symbols,
            "llm_config": config.llm_config,
            "exchange_config": config.exchange_config,
            "risk_config": config.risk_config,
            "system_prompt": config.system_prompt,
            "custom_system_prompt": config.custom_system_prompt,
            "custom_user_prompt": config.custom_user_prompt
        }
    except Exception as e:
        logger.error(f"获取trader配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'config' in locals():
            config.close()

@app.put("/api/traders/{trader_id}/config")
async def update_trader_config(
    trader_id: str,
    request: UpdateTraderConfigRequest
):
    """更新trader配置"""
    try:
        config = Config(trader_id=trader_id)
        
        if request.llm_config is not None:
            config.set_llm_config(request.llm_config)
        
        if request.exchange_config is not None:
            config.set_exchange_config(request.exchange_config)
        
        if request.risk_config is not None:
            config.set_risk_config(request.risk_config)
        
        if request.symbols is not None:
            db.execute("""
                UPDATE traders SET symbols = %s WHERE id = %s
            """, (json.dumps(request.symbols), trader_id))
        
        return {"message": "配置更新成功", "trader_id": trader_id}
    except Exception as e:
        logger.error(f"更新trader配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'config' in locals():
            config.close()

@app.get("/api/prompts/templates")
async def get_prompt_templates():
    """获取提示词模板列表"""
    try:
        templates = []
        prompts_dir = "prompts"
        
        if os.path.exists(prompts_dir):
            for file in os.listdir(prompts_dir):
                if file.endswith('.txt'):
                    name = file.replace('.txt', '')
                    try:
                        with open(os.path.join(prompts_dir, file), 'r', encoding='utf-8') as f:
                            content = f.read()
                            templates.append({
                                "name": name,
                                "description": content.split('\n')[0] if content else "",
                                "file": file
                            })
                    except Exception as e:
                        logger.error(f"读取模板文件失败 {file}: {e}")
        
        return {"templates": templates}
    except Exception as e:
        logger.error(f"获取提示词模板失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/traders/{trader_id}/prompts")
async def get_trader_prompts(trader_id: str):
    """获取trader的提示词配置"""
    try:
        config = Config(trader_id=trader_id)
        
        # 读取模板文件供参考
        templates = {}
        for template_name in ['aggressive', 'conservative']:
            file_path = f'prompts/{template_name}.txt'
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    templates[template_name] = f.read()
        
        # 可用的模板变量
        available_variables = [
            "critical_alerts", "position_data", "position_guide",
            "performance_signal", "historical_performance", "trading_guidance",
            "feedback_instructions", "frequency_control",
            "market_data", "signal_strength", "sentiment_section", "news_section",
            "risk_rules", "task_instructions",
            "coins", "win_rate", "stop_loss_pct", "take_profit_pct", "max_leverage"
        ]
        
        return {
            "system_prompt": config.system_prompt,
            "custom_system_prompt": config.custom_system_prompt,
            "custom_user_prompt": config.custom_user_prompt,
            "templates": templates,
            "available_variables": available_variables
        }
    except Exception as e:
        logger.error(f"获取trader提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'config' in locals():
            config.close()

@app.put("/api/traders/{trader_id}/prompts")
async def update_trader_prompts(
    trader_id: str,
    request: UpdatePromptsRequest
):
    """更新trader的提示词"""
    try:
        config = Config(trader_id=trader_id)
        config.set_custom_prompts(
            custom_system_prompt=request.custom_system_prompt,
            custom_user_prompt=request.custom_user_prompt
        )
        
        return {"message": "提示词更新成功"}
    except Exception as e:
        logger.error(f"更新提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'config' in locals():
            config.close()

# ===== Phase 3: Trader管理API =====

@app.get("/api/traders")
async def list_traders():
    """获取trader列表"""
    try:
        traders = db.execute("""
            SELECT 
                t.id, t.name, t.status, t.exchange, t.symbols,
                t.created_at, t.updated_at
            FROM traders t
            ORDER BY t.created_at DESC
        """)
        
        # 为每个trader获取统计数据
        result = []
        for trader in traders:
            stats = db.execute("""
                SELECT 
                    COUNT(CASE WHEN status = 'closed' THEN 1 END) as total_trades,
                    COUNT(CASE WHEN realized_pnl > 0 THEN 1 END) as winning,
                    COALESCE(SUM(realized_pnl), 0) as total_pnl
                FROM positions
                WHERE trader_id = %s
            """, (trader['id'],))
            
            stat = stats[0] if stats else {}
            total = stat.get('total_trades', 0)
            winning = stat.get('winning', 0)
            win_rate = winning / total if total > 0 else 0
            
            result.append({
                "id": str(trader['id']),
                "name": trader['name'],
                "status": trader['status'],
                "exchange": trader['exchange'],
                "symbols": trader['symbols'],
                "created_at": trader['created_at'].isoformat(),
                "updated_at": trader['updated_at'].isoformat(),
                "stats": {
                    "total_trades": total,
                    "win_rate": float(win_rate),
                    "total_pnl": float(stat.get('total_pnl', 0))
                }
            })
        
        return {"traders": result}
    except Exception as e:
        logger.error(f"获取trader列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/traders")
async def create_trader(request: CreateTraderRequest):
    """创建新的trader"""
    try:
        # 插入到traders表
        result = db.execute("""
            INSERT INTO traders 
            (name, exchange, symbols, llm_config, risk_config, 
             exchange_configs, system_prompt, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            request.name,
            'hyperliquid',  # 默认交易所
            json.dumps(request.symbols),
            json.dumps(request.llm_config),
            json.dumps(request.risk_config),
            json.dumps(request.exchange_config),
            request.system_prompt,
            'active'
        ))
        
        trader_id = str(result[0]['id']) if result else None
        
        return {
            "message": "Trader创建成功",
            "trader_id": trader_id
        }
    except Exception as e:
        logger.error(f"创建trader失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/traders/{trader_id}")
async def delete_trader(trader_id: str):
    """删除trader"""
    try:
        # 级联删除（数据库外键会自动处理）
        db.execute("""
            DELETE FROM traders WHERE id = %s
        """, (trader_id,))
        
        return {"message": "Trader删除成功"}
    except Exception as e:
        logger.error(f"删除trader失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/traders/{trader_id}/start")
async def start_trader(trader_id: str):
    """启动trader"""
    try:
        db.execute("""
            UPDATE traders SET status = %s WHERE id = %s
        """, ('running', trader_id))
        
        return {"message": "Trader已启动", "status": "running"}
    except Exception as e:
        logger.error(f"启动trader失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/traders/{trader_id}/stop")
async def stop_trader(trader_id: str):
    """停止trader"""
    try:
        db.execute("""
            UPDATE traders SET status = %s WHERE id = %s
        """, ('stopped', trader_id))
        
        return {"message": "Trader已停止", "status": "stopped"}
    except Exception as e:
        logger.error(f"停止trader失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 辅助功能端点 =====

@app.get("/api/competition")
async def get_competition(trader_id: str = Query(...)):
    """获取AI竞争数据"""
    try:
        competitions = db.execute("""
            SELECT 
                id, models_competed, winner_decision, 
                winner_model, winner_confidence, 
                competition_time, created_at
            FROM ai_competitions
            WHERE trader_id = %s
            ORDER BY created_at DESC
            LIMIT 20
        """, (trader_id,))
        
        result = []
        for comp in competitions:
            result.append({
                "id": str(comp['id']),
                "models_competed": comp['models_competed'],
                "winner_decision": comp['winner_decision'],
                "winner_model": comp['winner_model'],
                "winner_confidence": float(comp['winner_confidence']) if comp.get('winner_confidence') else 0.0,
                "competition_time": comp['competition_time'].isoformat() if comp.get('competition_time') else None,
                "created_at": comp['created_at'].isoformat()
            })
        
        return {"competitions": result}
    except Exception as e:
        logger.error(f"获取竞争数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/prompts/variables")
async def get_available_variables():
    """获取可用的模板变量列表"""
    return {
        "variables": {
            "critical_alerts": "紧急预警（持仓接近止损/止盈时）",
            "position_data": "当前持仓状态",
            "position_guide": "持仓操作指导（详细）",
            "performance_signal": "实时性能监控（夏普率、回撤等）",
            "historical_performance": "历史表现统计",
            "trading_guidance": "交易指导（基于胜率动态调整）",
            "feedback_instructions": "历史反馈学习指令（自动生成）",
            "frequency_control": "交易频率控制+连续止损暂停",
            "market_data": "完整市场数据（技术指标）",
            "signal_strength": "信号强度分析",
            "sentiment_section": "市场情绪指标",
            "news_section": "市场新闻",
            "risk_rules": "风控规则",
            "task_instructions": "任务说明",
            "coins": "可交易币种（逗号分隔）",
            "win_rate": "当前胜率（小数）",
            "stop_loss_pct": "止损百分比",
            "take_profit_pct": "止盈百分比",
            "max_leverage": "最大杠杆"
        }
    }

# ===== 迁移后的现有API（统一/api/*前缀） =====

@app.get("/api/market")
async def get_market(symbol: str = Query(...)):
    """获取市场数据和交易信号"""
    try:
        fetcher = CryptoFetcher(symbol=symbol)
        current_price = fetcher.get_current_price()
        df = fetcher.get_OHLCV()
        df = fetcher.get_technical_indicators(df)
        simple_prompt = fetcher.get_simple_trade_signal(df)
        
        # 提取最新的关键指标
        last_row = df.iloc[-1]
        
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
    except Exception as e:
        logger.error(f"获取市场数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_config(trader_id: str = Query(...)):
    """获取trader配置（兼容旧版）"""
    try:
        config = Config(trader_id=trader_id)
        return {
            "llm_config": config.llm_config,
            "exchange_config": config.exchange_config,
            "risk_config": config.risk_config,
            "system_prompt": config.system_prompt
        }
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'config' in locals():
            config.close()

@app.post("/api/config")
async def set_config(
    trader_id: str,
    llm_config: Optional[dict] = None,
    exchange_config: Optional[dict] = None,
    risk_config: Optional[dict] = None,
    system_prompt: Optional[str] = None
):
    """更新trader配置（兼容旧版）"""
    try:
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
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if 'config' in locals():
            config.close()

# ===== 回测API =====

@app.post("/api/backtest/run")
async def run_backtest(
    request: BacktestRequest,
    token: str = Depends(verify_token)
):
    """运行回测（需要认证）"""
    try:
        runner = BacktestRunner(
            trader_id=request.trader_id,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_balance=request.initial_balance,
            symbols=request.symbols,
            strategies=request.strategies,
            custom_prompt=request.custom_prompt
        )
        
        result = runner.run()
        
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"回测运行失败: {e}")
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

# ===== Hyperliquid配置管理API =====

@app.get("/api/hyperliquid/config")
async def get_hyperliquid_config():
    """获取Hyperliquid配置状态"""
    try:
        config = read_hyperliquid_config()
        
        if not config:
            return {
                "configured": False,
                "account_address": None,
                "message": "配置文件不存在"
            }
        
        return {
            "configured": True,
            "account_address": config.get('account_address'),
            # 不返回secret_key，安全考虑
            "message": "已配置"
        }
    except Exception as e:
        logger.error(f"获取Hyperliquid配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/hyperliquid/config")
async def update_hyperliquid_config(request: HyperliquidConfigRequest):
    """更新Hyperliquid配置"""
    try:
        # 验证地址格式
        if not validate_ethereum_address(request.account_address):
            raise HTTPException(
                status_code=400,
                detail="无效的以太坊地址格式（应为0x开头，42字符）"
            )
        
        # 验证私钥格式
        if not validate_private_key(request.secret_key):
            raise HTTPException(
                status_code=400,
                detail="无效的私钥格式（应为0x开头，66字符）"
            )
        
        # 写入配置
        success = write_hyperliquid_config(
            secret_key=request.secret_key,
            account_address=request.account_address
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="写入配置文件失败")
        
        return {
            "message": "Hyperliquid配置更新成功",
            "account_address": request.account_address
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新Hyperliquid配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hyperliquid/config/validate")
async def validate_hyperliquid_config(request: HyperliquidConfigRequest):
    """验证Hyperliquid配置是否有效"""
    try:
        # 验证格式
        if not validate_ethereum_address(request.account_address):
            return {
                "valid": False,
                "error": "无效的以太坊地址格式"
            }
        
        if not validate_private_key(request.secret_key):
            return {
                "valid": False,
                "error": "无效的私钥格式"
            }
        
        # 尝试连接测试
        # 临时写入配置
        temp_config_written = write_hyperliquid_config(
            secret_key=request.secret_key,
            account_address=request.account_address
        )
        
        if not temp_config_written:
            return {
                "valid": False,
                "error": "无法写入配置文件"
            }
        
        # 尝试获取账户余额
        try:
            hyperliquid = hyperliquidAPI()
            balance = hyperliquid.get_account_balance()
            
            if balance and balance.get('marginSummary'):
                equity = float(balance['marginSummary'].get('accountValue', 0))
                return {
                    "valid": True,
                    "message": "配置验证成功",
                    "account_equity": equity
                }
            else:
                return {
                    "valid": False,
                    "error": "无法获取账户信息，请检查配置"
                }
        except Exception as e:
            return {
                "valid": False,
                "error": f"连接Hyperliquid失败: {str(e)}"
            }
    except Exception as e:
        logger.error(f"验证Hyperliquid配置失败: {e}")
        return {
            "valid": False,
            "error": str(e)
        }

# ===== Hyperliquid工具API（保留现有功能） =====

@app.get("/api/hyperliquid/balance")
async def get_hyperliquid_balance():
    """获取Hyperliquid余额"""
    try:
        hyperliquid = hyperliquidAPI()
        balance = hyperliquid.get_account_balance()
        return {
            "balance": hyperliquid.contract_balance,
            "spot_balance": hyperliquid.spot_balance
        }
    except Exception as e:
        logger.error(f"获取余额失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hyperliquid/test-order")
async def post_hyperliquid_test_order(symbol: str):
    """测试订单"""
    try:
        hyperliquid = hyperliquidAPI()
        order = hyperliquid.test_order(symbol)
        return {"order": order}
    except Exception as e:
        logger.error(f"测试订单失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hyperliquid/close-all-positions")
async def post_hyperliquid_close_all_positions():
    """关闭所有持仓"""
    try:
        hyperliquid = hyperliquidAPI()
        positions = hyperliquid.close_all_positions()
        return {"positions": positions}
    except Exception as e:
        logger.error(f"关闭所有持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hyperliquid/close-position")
async def post_hyperliquid_close_position(symbol: str):
    """关闭指定持仓"""
    try:
        hyperliquid = hyperliquidAPI()
        position = hyperliquid.close_position(symbol)
        return {"position": position}
    except Exception as e:
        logger.error(f"关闭持仓失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hyperliquid/update-leverage")
async def post_hyperliquid_update_leverage(symbol: str, leverage: int):
    """更新杠杆"""
    try:
        hyperliquid = hyperliquidAPI()
        leverage_result = hyperliquid.update_leverage(symbol, leverage)
        return {"leverage": leverage_result}
    except Exception as e:
        logger.error(f"更新杠杆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===== 启动服务器 =====

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 启动 LangTrader API Server...")
    logger.info("📊 API文档: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
