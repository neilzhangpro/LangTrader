from langgraph.graph import StateGraph, START,END
from langchain.chat_models import init_chat_model
from typing import TypedDict, Annotated, List
from src.LangTrader.utils import logger
from src.LangTrader.config import Config


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
        return {"risk_passed": True}
    
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