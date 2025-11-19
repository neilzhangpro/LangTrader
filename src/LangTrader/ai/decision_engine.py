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
from src.LangTrader.market_sentiment import MarketSentiment
from src.LangTrader.ai.multi_ai_competition import MultiAICompetition
from src.LangTrader.ai.performance_tracker import RealTimePerformanceTracker

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
    sentiment_data:NotRequired[dict]
    global_news:NotRequired[list]
    coin_performance: NotRequired[dict]  # 🆕 币种表现分析
    smart_guidance: NotRequired[str]  # 🆕 智能指导
    competition_id: NotRequired[str]  # 🆕 竞争ID
    winner_model: NotRequired[str]  # 🆕 获胜模型
    performance_metrics: NotRequired[dict]
    performance_signal: NotRequired[str]



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
        self.fetcher = CryptoFetcher()
        self.symbols = config.symbols
        self.db = config.db
        self.market_analysis = MarketAnalysis(self.symbols)
        self.position_analysis = PositionAnalysis()
        self.hyperliquid = hyperliquidAPI()
        self.execute_decision = ExecuteDecision(self.config)
        self.historical_performance = HistoricalPerformance(self.config)
        self.prompt = Prompt(historical_performance_module=self.historical_performance)  # 🆕 传递历史模块
        self.sentiment_analysis = MarketSentiment()
        self.multi_ai_competition = MultiAICompetition(self.config)
        self.perf_tracker = RealTimePerformanceTracker(self.config.trader_id, self.db)

    def run(self, state:DecisionEngineState) -> DecisionEngineState:
        return self.runner.invoke(state)
    
    def _build_graph(self):
        self.graph.add_node("historical_performance", self._historical_performance)
        self.graph.add_node("real_time_performance", self._real_time_performance)
        self.graph.add_node("position_analysis", self._position_analysis)
        self.graph.add_node("risk_check", self._risk_check)
        self.graph.add_node("market_analysis", self._market_analysis)
        self.graph.add_node("multi_ai_competition", self._multi_ai_competition)
        self.graph.add_node("store_decision", self._store_decision)
        self.graph.add_node("execute_decision", self._execute_decision)
        self.graph.add_node("record_snapshot", self._record_snapshot)

        self.graph.add_edge(START, "historical_performance")
        self.graph.add_edge("historical_performance", "real_time_performance")
        self.graph.add_edge("real_time_performance", "position_analysis")
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
        self.graph.add_edge("market_analysis", "multi_ai_competition")
        self.graph.add_edge("multi_ai_competition", "store_decision")
    
        self.graph.add_conditional_edges(
            "store_decision",
            lambda state: "execute" if state["action"] in ["BUY", "SELL"] else "skip",
            {
                "execute": "execute_decision",  # BUY/SELL → 执行
                "skip": END                      # HOLD → 直接结束
            }
        )

        self.graph.add_edge("execute_decision", "record_snapshot")
        self.graph.add_edge("record_snapshot", END)

        return self.graph

    def _real_time_performance(self, state: DecisionEngineState) -> dict:
        """🆕 实时性能分析"""
        logger.info("-----Start Real-Time Performance Analysis------")
        
        try:
            # 计算性能指标
            metrics = self.perf_tracker.calculate_real_time_metrics(lookback_days=7)
            
            # 生成性能信号（传递metrics避免重复计算）
            performance_signal = self.perf_tracker.get_performance_signal(metrics)
            
            logger.info(f"📊 夏普率: {metrics['sharpe_ratio']:.2f}")
            logger.info(f"📊 最大回撤: {metrics['max_drawdown']:.1%}")
            logger.info(f"📊 性能状态: {metrics['performance_status']}")
            
            return {
                **state,
                "performance_metrics": metrics,
                "performance_signal": performance_signal
            }
        except Exception as e:
            logger.error(f"❌ 实时性能分析失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # 返回空信号，不影响后续流程
            return {
                **state,
                "performance_metrics": {},
                "performance_signal": ""
            }

    def _record_snapshot(self, state: DecisionEngineState) -> dict:
        """🆕 记录权益快照"""
        logger.info("-----Start Record Equity Snapshot------")
        
        try:
            account_balance = self.hyperliquid.get_account_balance()
            perf_tracker = self.perf_tracker
            perf_tracker.record_snapshot(
                account_balance=account_balance,
                decision_id=state.get("decision_id")
            )
            logger.info("✅ 权益快照已记录")
        except Exception as e:
            logger.error(f"❌ 记录快照失败: {e}")
        
        return state

    def _historical_performance(self, state: DecisionEngineState) -> DecisionEngineState:
        """🆕 增强的历史表现分析"""
        logger.info("-----Start Historical Performance (Enhanced)------")
        
        # 1. 获取基础历史数据
        recent_positions = self.historical_performance.get_20_position_info(state["trader_id"])
        recent_decisions = self.historical_performance.get_20_decision_info(state["trader_id"])
        
        # 2. 🆕 深度币种分析
        coin_performance = self.historical_performance.get_coin_performance_analysis(
            state["trader_id"]
        )
        
        # 3. 🆕 生成智能指导
        smart_guidance = self.historical_performance.generate_smart_guidance(
            coin_performance
        )
        
        logger.info(f"\n{smart_guidance}\n")
        
        # 4. 计算总体指标
        if not recent_positions:
            logger.warning("没有历史数据，使用默认值")
            return {
                **state,
                "historical_performance": {
                    "total_positions": 0,
                    "winning_positions": 0,
                    "losing_positions": 0,
                    "win_rate": 0.0
                },
                "coin_performance": {},
                "smart_guidance": "暂无历史数据，建议小仓位试探"
            }
        
        total_positions = len(recent_positions)
        winning_positions = len([p for p in recent_positions if p["realized_pnl"] > 0])
        losing_trades = len([p for p in recent_positions if p["realized_pnl"] < 0])
        
        metrics = {
            "total_positions": total_positions,
            "winning_positions": winning_positions,
            "losing_positions": losing_trades,
            "win_rate": winning_positions / total_positions if total_positions > 0 else 0,
            "recent_decisions": recent_decisions
        }
        
        return {
            **state,
            "historical_performance": metrics,
            "coin_performance": coin_performance,  # 🆕
            "smart_guidance": smart_guidance  # 🆕
        }
    
    def _multi_ai_competition(self, state: DecisionEngineState) -> dict:
        """🤖🤖🤖 多AI竞争节点（替换原来的 _llm_analysis）"""
        logger.info("-----Start Multi-AI Competition------")
        
        # 🆕 1. 确定 system_prompt（支持用户完全替换）
        if self.config.custom_system_prompt:
            system_prompt = self.config.custom_system_prompt
            logger.info("📝 使用自定义 system_prompt")
        else:
            system_prompt = self.config.system_prompt
            logger.info("📝 使用默认 system_prompt")
        
        # 🆕 2. 构建 user_prompt（支持用户自定义模板）
        if self.config.custom_user_prompt:
            # 用户自定义了模板，创建临时Prompt实例
            logger.info("📝 使用自定义 user_prompt 模板")
            custom_prompt_engine = Prompt(
                custom_template=self.config.custom_user_prompt,
                historical_performance_module=self.historical_performance
            )
            user_prompt = custom_prompt_engine.get_user_prompt(state, self.config, self.symbols)
        else:
            # 使用默认流程
            logger.info("📝 使用默认 user_prompt 生成流程")
            user_prompt = self.prompt.get_user_prompt(state, self.config, self.symbols)
        
        # 添加智能指导（如果有）
        if state.get("smart_guidance"):
            user_prompt += f"\n\n{state['smart_guidance']}"
        
        logger.debug(f"📊 最终提示词长度: system={len(system_prompt)}, user={len(user_prompt)}")
        
        # 3. 运行AI竞争
        competition_result = self.multi_ai_competition.run_competition(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            trader_id=state["trader_id"]
        )
        
        winner_decision = competition_result['winner_decision']
        
        return {
            **state,
            "symbol": winner_decision['symbol'],
            "action": winner_decision['action'],
            "side": winner_decision['side'],
            "confidence": winner_decision['confidence'],
            "leverage": winner_decision['leverage'],
            "llm_analysis": winner_decision['analysis'],
            "competition_id": competition_result['competition_id'],  # 🆕
            "winner_model": competition_result['winner_model']  # 🆕
        }
    
    def _store_decision(self, state: DecisionEngineState) -> dict:
        """存储决策（🆕 关联competition_id和winner_model）"""
        logger.info("-----Start Store Decision------")
        
        try:
            import json
            
            market_data_json = json.dumps({
                "text": state.get("market_data", "")[:500]
            })
            
            indicators_json = json.dumps(state.get("indicators", {}))
            
            llm_analysis_json = json.dumps({
                "analysis": state.get("llm_analysis", ""),
                "side": state.get("side", "none"),
                "leverage": state.get("leverage", 1)
            })
            
            result = self.db.execute("""
                INSERT INTO decisions 
                (trader_id, symbol, market_data, indicators, llm_analysis,
                action, confidence, risk_passed, executed,
                competition_id, winner_model)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                state.get("executed", False),
                state.get("competition_id"),  # 🆕
                state.get("winner_model")  # 🆕
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
        
        # 获取情绪数据（每个币种）
        sentiment_data = {}
        for symbol in self.symbols:
            try:
                sentiment = self.sentiment_analysis.get_all_sentiment_data(symbol)
                sentiment_data[symbol] = sentiment
                logger.info(f"{symbol} 情绪数据: FNG={sentiment['fear_greed_index']['value']}")
            except Exception as e:
                logger.error(f"获取{symbol}情绪数据失败: {e}")
                sentiment_data[symbol] = None
        
        # 获取全局市场新闻（只获取一次）
        global_news = []
        try:
            global_news = self.sentiment_analysis.get_global_news(limit=5)
            logger.info(f"✅ 获取到 {len(global_news)} 条全局市场新闻")
            
            # 调试：打印新闻内容
            if global_news:
                logger.info("📰 新闻详情:")
                for i, news in enumerate(global_news, 1):
                    logger.info(f"  {i}. [{news.get('source', '')}] {news.get('title', '')[:60]}")
            else:
                logger.warning("⚠️ global_news 列表为空")
                
        except Exception as e:
            logger.error(f"获取全局新闻失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return {
            **state,
            "market_data": market_data,
            "indicators": key_indicators,
            "sentiment_data": sentiment_data,
            "global_news": global_news
        }

  
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
        logger.info(f"User Prompt: {user_prompt}")
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