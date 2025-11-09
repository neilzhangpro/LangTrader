from langgraph.graph import StateGraph, START,END
from langchain.chat_models import init_chat_model
from typing import TypedDict, Annotated, List
from src.LangTrader.utils import logger
from src.LangTrader.config import Config
from src.LangTrader.hyperliquidExchange import hyperliquidAPI


class DecisionEngineState(TypedDict):
    trader_id:str
    symbol:str
    market_data:dict
    indicators:dict
    postion_info:dict
    action:bool
    risk_passed:bool
    confidence:float
    leverage:int
    llm_analysis:str

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

    def run(self, state:DecisionEngineState) -> DecisionEngineState:
        return self.runner.invoke(state)
    
    def _build_graph(self):
        self.graph.add_node("risk_check", self._risk_check)
        self.graph.add_node("market_analysis", self._market_analysis)
        self.graph.add_node("llm_analysis", self._llm_analysis)

        self.graph.add_edge(START, "risk_check")
        self.graph.add_edge("risk_check", "market_analysis")
        self.graph.add_edge("market_analysis", "llm_analysis")
        self.graph.add_edge("llm_analysis", END)

        return self.graph

    
    def _risk_check(self, state:DecisionEngineState) -> DecisionEngineState:
        logger.info("-----Strat Risk Check------")
        #get the risk config
        risk_config = self.config.risk_config
        #account balance check
        account_balance = self.hyperliquid.get_account_balance()
        if not account_balance:
            logger.error("Failed to get account balance")
            return {
                **state,
                "risk_passed": False
            }
        withdrawable = float(account_balance["marginSummary"]["totalRawUsd"])
        if  withdrawable < 10:
            logger.info("Account balance is less than 10")
            return {
                **state,
                "risk_passed": False
            }
        #max position size check
        # 检查当前仓位占比是否超限
        max_position_ratio = risk_config.get("max_position_size", 0.1)  # 10%
        total_position_value = float(account_balance.get("marginSummary", {}).get("totalNtlPos", 0))
        account_value = float(account_balance.get("marginSummary", {}).get("accountValue", 1))

        current_position_ratio = total_position_value / account_value if account_value > 0 else 0

        if current_position_ratio >= max_position_ratio:
            logger.warning(f"仓位占比 {current_position_ratio:.1%} >= 限制 {max_position_ratio:.1%}")
            return {**state, "risk_passed": False}
        #leverage check
        leverage = risk_config["max_leverage"]
        if state["leverage"] > leverage:
            logger.info("Leverage is greater than the max leverage")
            return {
                **state,
                "risk_passed": False
            }
        #margin_used check
        margin_used = float(account_balance["marginSummary"]["totalMarginUsed"])
        account_value = float(account_balance.get("marginSummary", {}).get("accountValue", 1))
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
            "risk_passed": True
        }
    
    def _market_analysis(self, state:DecisionEngineState) -> DecisionEngineState:
        return {"market_data": state["market_data"]}
    
    def _llm_analysis(self, state:DecisionEngineState) -> DecisionEngineState:
        system_prompt = self.config.system_prompt
        result = self.model.invoke(system_prompt)
        logger.info(f"LLM analysis result: {result}")
        return {
            "llm_analysis": state["llm_analysis"],
            "confidence": state["confidence"],
            "leverage": state["leverage"],
            "action": state["action"]
            }