from langgraph.graph import StateGraph, START,END
from langchain.chat_models import init_chat_model
from typing import TypedDict, Annotated, List, NotRequired
from src.LangTrader.utils import logger
from src.LangTrader.config import Config
from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from src.LangTrader.market import CryptoFetcher
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from src.LangTrader.db import Database
from src.LangTrader.ai.market_analysis import MarketAnalysis
from src.LangTrader.ai.position_analysis import PositionAnalysis
from src.LangTrader.ai.prompt import Prompt
from src.LangTrader.ai.execute_decision import ExecuteDecision
from src.LangTrader.ai.historical_performance import HistoricalPerformance

class DecisionEngineState(TypedDict):
    trader_id:str
    symbol:str
    market_data:str
    indicators:dict
    postion_info:dict
    action:str
    side:str
    risk_passed:bool
    confidence:float
    leverage:int
    historical_performance:dict
    llm_analysis:str
    executed:bool
    position_data:NotRequired[str]
    current_positions:NotRequired[dict]
    account_balance:NotRequired[dict]
    decision_id:NotRequired[str]
    executed_intent:NotRequired[str]


class TradingDecision(BaseModel):
    """LLM 结构化输出模型"""
    symbol: str = Field(description="选择的交易币种，如 BTC, ETH")
    action: str = Field(description="交易动作: BUY, SELL, 或 HOLD")
    side: str = Field(description="方向: long 或 short，如果是 HOLD 则为 none")
    confidence: float = Field(description="决策置信度，范围 0.0 到 1.0", ge=0.0, le=1.0)
    leverage: int = Field(description="建议杠杆倍数，范围 1 到 10", ge=1, le=10)
    analysis: str = Field(description="决策分析理由")

class DecisionEngine:
    def __init__(self, config: Config):
        self.config = config
        logger.info(f"LLM Config: {config.llm_config}")
        print(config.llm_config["openai"]["model"])
        model_name = config.llm_config["openai"]["model"]
        api_key = config.llm_config["openai"]["api_key"]
        base_url = config.llm_config["openai"]["base_url"]
        self.model = init_chat_model(model=model_name, api_key=api_key, base_url=base_url)
        logger.info(f"Model: {self.model}")
        self.graph = StateGraph(DecisionEngineState)
        self.graph = self._build_graph()
        self.runner = self.graph.compile()
        self.hyperliquid = hyperliquidAPI()
        self.fetcher = CryptoFetcher()
        self.symbols = config.symbols
        self.db = Database()
        self.market_analysis = MarketAnalysis(self.symbols)
        self.position_analysis = PositionAnalysis()
        self.prompt = Prompt()
        self.execute_decision = ExecuteDecision(self.config)
        self.historical_performance = HistoricalPerformance(self.config)

    def run(self, state:DecisionEngineState) -> DecisionEngineState:
        return self.runner.invoke(state)
    
    def _build_graph(self):
        self.graph.add_node("historical_performance", self._historical_performance)
        self.graph.add_node("position_analysis", self._position_analysis)
        self.graph.add_node("risk_check", self._risk_check)
        self.graph.add_node("market_analysis", self._market_analysis)
        self.graph.add_node("llm_analysis", self._llm_analysis)
        self.graph.add_node("store_decision", self._store_decision)
        self.graph.add_node("execute_decision", self._execute_decision)

        self.graph.add_edge(START, "historical_performance")
        self.graph.add_edge("historical_performance", "position_analysis")
        self.graph.add_edge("position_analysis", "risk_check")
        #add condition edge
        self.graph.add_conditional_edges(
            "risk_check",
            lambda state: state["risk_passed"],
            {
                True: "market_analysis",
                False: "store_decision"
            }
        )
        self.graph.add_edge("market_analysis", "llm_analysis")
        self.graph.add_edge("llm_analysis", "store_decision")
    
        self.graph.add_conditional_edges(
            "store_decision",
            lambda state: "execute" if state["action"] in ["BUY", "SELL"] else "skip",
            {
                "execute": "execute_decision",  # BUY/SELL → 执行
                "skip": END                      # HOLD → 直接结束
            }
        )
        self.graph.add_edge("execute_decision", END)

        return self.graph

    def _historical_performance(self, state:DecisionEngineState) -> DecisionEngineState:
        logger.info("-----Start Historical Performance------")
        recent_positions = self.historical_performance.get_20_position_info(state["trader_id"])
        recent_decisions = self.historical_performance.get_20_decision_info(state["trader_id"])
        if not recent_positions:
            logger.warning("没有历史数据，使用默认值")
            return {
                **state,
                "historical_performance": {
                    "total_positions": 0,
                    "winning_positions": 0,
                    "losing_positions": 0,
                    "win_rate": 0.0
                }
            }
        if not recent_decisions:
            logger.warning("No recent decisions found")
            return {
                **state,
                "historical_performance": {
                    "total_positions": 0,
                    "winning_positions": 0,
                    "losing_positions": 0,
                    "win_rate": 0.0
                }
            }
        #calculate the historical performance
        metrics ={}
        #win rate
        total_positions = len(recent_positions)
        winning_positions = len([position for position in recent_positions if position["realized_pnl"] > 0])
        losing_trades = len([position for position in recent_positions if position["realized_pnl"] < 0])

        #total pnl
        metrics["total_positions"] = total_positions
        metrics["winning_positions"] = winning_positions
        metrics["losing_positions"] = losing_trades
        metrics["win_rate"] = winning_positions / total_positions if total_positions > 0 else 0
        #recent decisions analysis
        metrics["recent_decisions"] = recent_decisions
        return {
            **state,
            "historical_performance": metrics
        }

            
    def _risk_check(self, state:DecisionEngineState) -> DecisionEngineState:
        logger.info("-----Strat Risk Check------")
        #get the risk config
        risk_config = self.config.risk_config
        #account balance check
        account_balance = state.get("account_balance") or self.hyperliquid.get_account_balance()
        if not account_balance:
            logger.error("Failed to get account balance")
            return {
                **state,
                "risk_passed": False
            }
        #get postion info
        postion_info = account_balance.get("assetPositions", [])
        margin_summary = account_balance.get("marginSummary", {}) or {}
        withdrawable = float(account_balance.get("withdrawable") or margin_summary.get("withdrawable", 0) or 0)
        if  withdrawable < 10:
            logger.info("Account balance is less than 10")
            return {
                **state,
                "risk_passed": False
            }
        #max position size check
        current_action = (state.get("action") or "").upper()
        current_side = (state.get("side") or "").lower()
        is_open_intent = current_action == "BUY" and current_side in {"long", "short"}

        max_position_ratio = risk_config.get("max_position_size", 0.1)  # 10%
        total_position_value = float(margin_summary.get("totalNtlPos", 0))
        account_value = float(margin_summary.get("accountValue", 1))
        current_position_ratio = total_position_value / account_value if account_value > 0 else 0

        if is_open_intent and current_position_ratio >= max_position_ratio:
            logger.warning(
                f"仓位占比 {current_position_ratio:.1%} >= 限制 {max_position_ratio:.1%}，禁止继续加仓"
            )
            return {**state, "risk_passed": False}

        if not is_open_intent and current_position_ratio >= max_position_ratio:
            logger.info(
                f"仓位占比 {current_position_ratio:.1%} 已超过限制，但当前指令为平仓/减仓，允许继续执行"
            )
        #margin_used check
        margin_used = float(margin_summary.get("totalMarginUsed", 0))
        account_value = float(margin_summary.get("accountValue", 1))
        margin_ration = margin_used / account_value if account_value > 0 else 0
        if margin_ration > 0.85:
            logger.info("Margin used is greater than 85%")
            return {
                **state,
                "risk_passed": False
            }
        logger.info("-----End Risk Check------")

        return {
            **state,
            "risk_passed": True,
            "postion_info": postion_info
        }
    
    def _position_analysis(self, state: DecisionEngineState) -> dict:
        """分析当前持仓状态，为 LLM 提供持仓上下文"""
        logger.info("-----Start Position Analysis------")

        try:
            result = self.position_analysis.get_position_analysis(state)
            return result
        except Exception as e:
            logger.error(f"持仓分析失败: {e}")
            return {
                **state,
                "position_data": f"持仓分析失败: {e}",
                "current_positions": {},
                "account_balance": None
            }

    def _market_analysis(self, state: DecisionEngineState) -> dict:
        """市场分析 - 提取关键指标"""
        logger.info("-----Start Market Analysis------")
        logger.info(f"Symbols: {self.symbols}")
        market_data, key_indicators = self.market_analysis.get_market_data(state)
        return {
            **state,
            "market_data": market_data,
            "indicators": key_indicators  # 现在可以安全序列化了
        }

    def _store_decision(self, state: DecisionEngineState) -> dict:
        """存储决策到数据库"""
        logger.info("-----Start Store Decision------")
        
        try:
            import json
            
            # 准备 JSONB 字段
            market_data_json = json.dumps({
                "text": state.get("market_data", "")[:500]  # 简化存储
            })
            
            indicators_json = json.dumps(state.get("indicators", {}))
            
            llm_analysis_json = json.dumps({
                "analysis": state.get("llm_analysis", ""),
                "side": state.get("side", "none"),  # side 存在这里
                "leverage": state.get("leverage", 1)  # leverage 存在这里
            })
            
            result = self.db.execute("""
                INSERT INTO decisions 
                (trader_id, symbol, market_data, indicators, llm_analysis,
                action, confidence, risk_passed, executed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                state["trader_id"],
                state["symbol"],
                market_data_json,
                indicators_json,
                llm_analysis_json,
                state.get("action", "HOLD"),
                state.get("confidence", 0.0),
                state.get("risk_passed", False),
                state.get("executed", False)
            ))
            
            decision_id = result[0]['id'] if result else None
            logger.info(f"✅ Decision stored with ID: {decision_id}")
            
            return {
                **state,
                "decision_id": decision_id
            }
            
        except Exception as e:
            logger.error(f"❌ Store decision failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {**state}

    def _execute_decision(self, state:DecisionEngineState) -> dict:
        logger.info("-----Start Execute Decision------")
        result = self.execute_decision.execute_decision(state)
        return result
    
    def _llm_analysis(self, state: DecisionEngineState) -> dict:
        """LLM 分析（使用结构化输出）"""
        logger.info("-----Start LLM Analysis------")
        
        # 创建结构化输出模型
        structured_llm = self.model.with_structured_output(TradingDecision)
        
        system_prompt = self.config.system_prompt
        coin_list = ", ".join(self.symbols)
        
        # 构建 prompt
        user_prompt = self.prompt.get_user_prompt(state,self.config,self.symbols)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        # 调用 LLM 获取结构化输出
        try:
            decision = structured_llm.invoke(messages)
            
            logger.info(f"LLM Decision: {decision.action} {decision.symbol} @ confidence {decision.confidence}")
            logger.info(f"Side: {decision.side}, Leverage: {decision.leverage}x")
            logger.info(f"Analysis: {decision.analysis[:100]}...")
            
            return {
                **state,
                "symbol": decision.symbol,
                "action": decision.action,
                "side": decision.side,
                "confidence": decision.confidence,
                "leverage": decision.leverage,
                "llm_analysis": decision.analysis
            }
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                **state,
                "action": "HOLD",
                "side": "none",
                "confidence": 0.0,
                "leverage": 0,
                "llm_analysis": f"Analysis failed: {str(e)}"
            }