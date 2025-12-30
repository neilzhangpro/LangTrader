from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import State, RunRecord
from langtrader_core.utils import get_logger
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import uuid
from typing import Dict, Any
import asyncio

logger = get_logger("market_analyzer")

class MarketAnalyzerNode(NodePlugin):
    """
    Market Analyzer Node
    """
    metadata = NodeMetadata(
        name="market_analyzer",
        display_name="Market Analyzer",
        version="1.0.0",
        author="LangTrader official",
        description="Market Analyzer Node",
        category="analysis",
        tags=["ai", "analysis"],
        inputs=["symbols", "market_data"],
        outputs=["market_analysis"],
        requires=["market_state"],
        requires_llm=True,
        # 🎯 只用 insert_after，避免目标节点不存在的问题
        insert_after="quant_signal_filter",
        suggested_order=4,
        auto_register=True
    )

    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        #check if llm factory is in context
        if not context:
            logger.error("🚨 Context not found")
            raise ValueError("Context not found")
        if not hasattr(context, 'llm_factory') or context.llm_factory is None:
            logger.error("🚨 LLM factory not found in context")
            raise ValueError("LLM factory not found in context")
        
        # try to build llm
        try:
            self.llm = context.llm_factory.create_default()
            logger.info(f"✅ LLM created: {self.llm.model_name}")
        except Exception as e:
            logger.error(f"🚨 Failed to create LLM: {e}")
            raise RuntimeError(
                f"❌ Failed to create LLM: {e}\n"
                f"Please check:\n"
                f"1) Database has LLM configs: SELECT * FROM llm_configs WHERE is_enabled=true\n"
                f"2) At least one is default: SELECT * FROM llm_configs WHERE is_default=true\n"
                f"3) API keys are configured correctly"
            ) from e
        
        # create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            # using the analysis_prompt as the user prompt
            ("user", "{analysis_prompt}")
        ])
        #build chain
        self.chain = self.prompt | self.llm
        logger.info(f"✅ Chain built: {self.chain}")

    async def run(self, state: State) -> State:
        """
        Run the market analyzer node
        """
        logger.info("📊 Market Analyzer started")
        
        analyzed_count = 0
        
        # 为每个币种单独分析
        for symbol in state.symbols:
            try:
                # 获取该币种的市场数据
                symbol_data = state.market_data.get(symbol, {})
                indicators = symbol_data.get('indicators', {})
                
                if not indicators:
                    logger.warning(f"No indicators for {symbol}")
                    continue
                
                # 生成该币种的分析 prompt
                user_prompt = self._get_symbol_prompt(symbol, indicators)
                
                try:
                    response = await asyncio.wait_for(
                        self.chain.ainvoke({"analysis_prompt": user_prompt}),
                        timeout=60.0  # 60秒超时
                    )
                    analysis_result = response.content
                except Exception as e:
                    logger.error(f"❌ {symbol}: LLM call timed out (60s): {e}")
                    analysis_result = "Analysis timed out - market data unavailable"
                
                # 确保 RunRecord 存在
                if symbol not in state.runs:
                    state.runs[symbol] = RunRecord(
                        run_id=str(uuid.uuid4()),
                        cycle_id=str(state.bot_id),
                        symbol=symbol,
                        cycle_time=datetime.now()
                    )
                
                # 🎯 存储分析结果到 RunRecord
                state.runs[symbol].market_analysis = analysis_result
                state.runs[symbol].analyzed_at = datetime.now().isoformat()
                
                analyzed_count += 1
                logger.info(f"✅ {symbol}: {analysis_result[:60]}...")
                
            except Exception as e:
                logger.error(f"Failed to analyze {symbol}: {e}")
                continue
        
        logger.info(f"✅ Market Analyzer finished: {analyzed_count}/{len(state.symbols)} analyzed")
        return state
    
    def _get_symbol_prompt(self, symbol: str, indicators: Dict[str, Any]) -> str:
        """
        为单个币种生成分析 prompt（增强版）
        """
        # 1. 量化信号得分（来自预处理节点）
        quant_signal = indicators.get('quant_signal', {})
        
        prompt = f"""Analyze {symbol}:

**Quantitative Signal Pre-filter**:
- Total Score: {quant_signal.get('total_score', 'N/A')}/100
- Breakdown: Trend={quant_signal.get('breakdown', {}).get('trend', 'N/A')}, Momentum={quant_signal.get('breakdown', {}).get('momentum', 'N/A')}, Volume={quant_signal.get('breakdown', {}).get('volume', 'N/A')}, Sentiment={quant_signal.get('breakdown', {}).get('sentiment', 'N/A')}
- Key Signals: {', '.join(quant_signal.get('reasons', []))}

**Technical Indicators**:
"""
        
        # 2. 当前指标值
        for key, value in indicators.items():
            if key not in ('quant_signal',):
                prompt += f"- {key}: {self._format_value(value)}\n"
        
        prompt += """
Provide comprehensive market analysis including:
- Trend alignment across timeframes
- Momentum strength and direction
- Volume confirmation
- Key support/resistance levels
- Risk assessment
"""
        
        return prompt
        
    def _format_value(self, value) -> str:
        """格式化指标值"""
        if value is None or value == 'N/A':
            return "N/A"
        
        if isinstance(value, dict):
            if not value:  # 空字典
                return "N/A"
            # 格式化字典
            parts = []
            for k, v in value.items():
                if isinstance(v, (int, float)):
                    parts.append(f"{k}:{v:.4f}")
                else:
                    parts.append(f"{k}:{v}")
            return "{" + ", ".join(parts) + "}"
        
        if isinstance(value, (int, float)):
            return f"{value:.4f}"
        
        return str(value)

    def _get_system_prompt(self):
        return """ you are a professional market analyzer, your ablity is to analyze the market data and generate a seirous discrption of current market situation. Those discrptions will be used in a real trading decision by a trader.
        You will be given many trade signals and indicators,
        such as ema, macd, rsi, etc. Analyze them and refer regarding market analysis metrics, such as trend, momentum, volatility, volume,support, resistance, risk, opportunity,multiple timeframes, etc.
        Your final output must include all or some of the metrics and simple description we mentioned above.
        Your output must be in the following format:
        [metrics]: what the metrics is and what the value is.
        [description]: a simple description of the market situation.
        Example:
        [trend]: the BTC is in a strong uptrend
        [description]: the BTC is in a strong uptrend, the trend is strong and the momentum is strong.
        Below is the market data:
        """