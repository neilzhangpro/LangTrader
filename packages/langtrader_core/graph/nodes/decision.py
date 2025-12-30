from langtrader_core.graph.state import State, AIDecision, PerformanceMetrics
from langtrader_core.utils import get_logger
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langchain_core.messages import HumanMessage, SystemMessage
from pathlib import Path
import json

logger = get_logger("decision")


class Decision(NodePlugin):
    """
    The node that makes the decision.
    """
    metadata = NodeMetadata(
        name="decision",
        display_name="Decision",
        version="1.0.0",
        author="LangTrader official",
        description="The node that makes the decision.",
        category="Basic",
        tags=["decision", "official"],
        insert_after="market_analyzer",
        suggested_order=5,
        auto_register=True 
    )

    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        self.llm_factory = context.llm_factory if context and hasattr(context, 'llm_factory') else None
        self.database = context.database if context else None
        self.trader = context.trader if context else None
        self.stream_manager = context.stream_manager if context else None
        self.performance_service = context.performance_service if context else None
        self.llm_with_structure = None

    def _create_llm(self):
        if self.llm_factory is None:
            logger.warning("No LLM factory found")
            raise ValueError("No LLM factory found")
        try:
            llm_instance = self.llm_factory.create_default()
            llm = llm_instance.with_structured_output(AIDecision)
            return llm
        except Exception as e:
            logger.error(f"🚨 Failed to create LLM with structured output: {e}")
            raise ValueError(f"🚨 Failed to create LLM with structured output: {e}")

    def _load_prompts(self, filename):
        logger.info(f"Loading prompts from {filename}")
        current_dir = Path(__file__).parent
        prompts_dir = current_dir.parent.parent / "prompts"
        file_path = prompts_dir / filename

        if not file_path.exists():
            logger.warning(f"🚨 Prompt file not found: {file_path}")
            return ""

        content = file_path.read_text(encoding='utf-8')
        if not content:
            logger.warning(f"🚨 No prompts found in {filename}")

        return content

    def _format_output_with_examples(self, symbol: str = None):
        """输出格式要求（包含Few-Shot案例）"""
        
        schema = AIDecision.model_json_schema()
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
        
        symbol_hint = f"for {symbol}" if symbol else ""
        
        return f"""
# Decision Making Guidelines {symbol_hint}

## Case Study 1: Strong Trend Breakout → Open Long
**Market State**:
- Quant Score: 85/100 (Trend:90, Momentum:85, Volume:80, Sentiment:70)
- 3m/4h EMA alignment: bullish (price > EMA20_3m > EMA20_4h)
- MACD: golden cross on both timeframes
- Volume: 2.3x average (confirming breakout)
- Funding Rate: 0.03% (healthy, not overleveraged)

**Decision**:
{{
  "symbol": "{symbol or 'BTC/USDT:USDT'}",
  "action": "open_long",
  "leverage": 3,
  "position_size_usd": 100,
  "stop_loss_price": 95.0,
  "take_profit_price": 115.0,
  "confidence": 85,
  "risk_usd": 15.0,
  "reasons": [
    "Multi-timeframe trend alignment (Quant Trend=90)",
    "Volume breakout confirms strength (2.3x avg)",
    "MACD/RSI both support upward move",
    "Healthy funding rate, no extreme sentiment"
  ]
}}

## Case Study 2: Weak Signal → Wait
**Market State**:
- Quant Score: 45/100 (filtered by pre-processor but passed threshold)
- 3m shows uptrend but 4h RSI: 78 (overbought)
- Volume declining (0.6x average - divergence warning)
- Sharpe Ratio: -0.3 (recent underperformance period)
- Funding Rate: 0.12% (extremely high, longs overleveraged)

**Decision**:
{{
  "symbol": "{symbol or 'BTC/USDT:USDT'}",
  "action": "wait",
  "leverage": 1,
  "position_size_usd": 0,
  "confidence": 40,
  "reasons": [
    "Low quant score (45/100) indicates weak setup",
    "Overbought on 4h timeframe (RSI=78)",
    "Volume divergence - price up but volume down",
    "Negative Sharpe ratio suggests waiting for better conditions",
    "Extremely high funding rate (0.12%) - market overleveraged"
  ]
}}

## Case Study 3: Close Position (Take Profit)
**Market State**:
- Current position: Long from 100, now at 110 (+10%)
- Quant Score dropped from 85 to 55
- MACD 3m formed death cross
- Volume consistently declining for 3 periods
- Target was 120, but momentum weakening

**Decision**:
{{
  "symbol": "{symbol or 'BTC/USDT:USDT'}",
  "action": "close_long",
  "confidence": 75,
  "reasons": [
    "Captured 10% profit, momentum weakening",
    "MACD death cross signals trend reversal",
    "Volume decline suggests uptrend exhaustion",
    "Quant score dropped 30 points - setup deteriorating",
    "Better to secure profit than risk reversal"
  ]
}}

## Your Output Format
{schema_str}

## Critical Rules
1. **Risk-Reward Ratio ≥ 3:1 (STRICT)**
   - Long: Risk = Entry - StopLoss, Profit = TakeProfit - Entry
   - Short: Risk = StopLoss - Entry, Profit = Entry - TakeProfit
   - R:R = Profit / Risk must be ≥ 3.0

2. **Consider Quantitative Signal Score**
   - Higher score (>70) = stronger setup
   - Lower score (<50) = be more cautious
   - Use breakdown to understand why

3. **Use Funding Rate as Sentiment Indicator**
   - > 0.1%: Market overleveraged long (caution for longs)
   - < -0.05%: Opportunity to get paid holding long
   - -0.01% to 0.05%: Healthy range

4. **Respect Performance Feedback**
   - Sharpe < -0.5: STOP trading, only wait
   - Sharpe < 0: Be very selective, high confidence only
   - Sharpe > 0.7: Can be more aggressive

5. **Stop-Loss and Take-Profit Logic**
   - Long: stop_loss < entry < take_profit
   - Short: take_profit < entry < stop_loss
"""

    def _format_single_symbol_prompt(
        self, 
        state: State, 
        symbol: str, 
        run_record,
        performance: PerformanceMetrics = None
    ) -> str:
        """
        为单个 symbol 构建决策 prompt（增强版）
        """
        prompts = ""
        
        # 1. 绩效信息（如果有）
        if performance and performance.total_trades > 0:
            prompts += performance.to_prompt_text()
            prompts += "\n"
        
        # 2. 账户信息
        prompts += "Account info:\n"
        prompts += "-------------------\n"
        if state.account:
            prompts += f"Total: {state.account.total}\n"
            prompts += f"Free: {state.account.free}\n"
        prompts += f"Initial balance before cycle: {state.initial_balance}\n"
        prompts += "-------------------\n\n"
        
        # 3. 持仓信息（只显示当前 symbol 相关的持仓）
        prompts += "Position info:\n"
        prompts += "-------------------\n"
        symbol_positions = [p for p in state.positions if p.symbol == symbol]
        if symbol_positions:
            for pos in symbol_positions:
                prompts += f"  Symbol: {pos.symbol}\n"
                prompts += f"  Side: {pos.side}, Amount: {pos.amount}\n"
                prompts += f"  Entry: {pos.price}, SL: {pos.stop_loss_price}, TP: {pos.take_profit_price}\n"
        else:
            prompts += "No position for this symbol\n"
        prompts += "-------------------\n\n"
        
        # 4. 量化信号评分（新增）
        market_data = state.market_data.get(symbol, {})
        indicators = market_data.get('indicators', {})
        quant_signal = indicators.get('quant_signal', {})
        
        if quant_signal:
            prompts += "Quantitative Signal Analysis:\n"
            prompts += "-------------------\n"
            prompts += f"  Overall Score: {quant_signal.get('total_score', 'N/A')}/100\n"
            prompts += f"  Breakdown:\n"
            breakdown = quant_signal.get('breakdown', {})
            prompts += f"    - Trend: {breakdown.get('trend', 'N/A')}\n"
            prompts += f"    - Momentum: {breakdown.get('momentum', 'N/A')}\n"
            prompts += f"    - Volume: {breakdown.get('volume', 'N/A')}\n"
            prompts += f"    - Sentiment: {breakdown.get('sentiment', 'N/A')}\n"
            prompts += f"  Key Signals: {', '.join(quant_signal.get('reasons', []))}\n"
            prompts += "-------------------\n\n"
        
        # 5. 资金费率（新增）
        funding_rate = indicators.get('funding_rate', 0)
        if funding_rate is not None:
            prompts += "Funding Rate:\n"
            prompts += "-------------------\n"
            prompts += f"  Current Rate: {funding_rate*100:.4f}% per 8h\n"
            
            if funding_rate > 0.1:
                prompts += "  ⚠️ Warning: Extremely high funding rate (longs pay shorts)\n"
                prompts += "  → Market is overleveraged long, consider shorting\n"
            elif funding_rate < -0.05:
                prompts += "  💡 Opportunity: Negative funding rate (shorts pay longs)\n"
                prompts += "  → You get paid to hold long positions\n"
            elif -0.01 < funding_rate < 0.05:
                prompts += "  ✅ Healthy funding rate range\n"
            
            prompts += "-------------------\n\n"
        
        # 6. 市场分析（当前 symbol）
        prompts += f"[{symbol}]\n"
        prompts += "--------------\n"
        market_analysis = getattr(run_record, 'market_analysis', None)
        prompts += f"{market_analysis}\n"
        cycle_id = getattr(run_record, 'cycle_id', None)
        prompts += f"Cycle id: {cycle_id}\n"
        prompts += "--------------\n\n"
        
        # 7. 输出格式要求（添加案例）
        prompts += self._format_output_with_examples(symbol)
        
        return prompts

    async def run(self, state: State) -> State:
        system_prompt = self._load_prompts(state.prompt_name)
        
        # 计算绩效指标
        performance = None
        if self.performance_service:
            try:
                performance = self.performance_service.calculate_metrics(state.bot_id)
                # 保存到 state（Pydantic 版本）
                state.performance = PerformanceMetrics(
                    total_trades=performance.total_trades,
                    winning_trades=performance.winning_trades,
                    losing_trades=performance.losing_trades,
                    win_rate=performance.win_rate,
                    avg_return_pct=performance.avg_return_pct,
                    total_return_usd=performance.total_return_usd,
                    sharpe_ratio=performance.sharpe_ratio,
                    max_drawdown=performance.max_drawdown,
                    avg_win_pct=performance.avg_win_pct,
                    avg_loss_pct=performance.avg_loss_pct,
                    profit_factor=performance.profit_factor,
                )
                logger.info(f"📊 Performance loaded: sharpe={performance.sharpe_ratio:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load performance: {e}")
        
        for symbol, run_record in state.runs.items():
            # 为每个 symbol 构建独立 prompt（包含绩效信息）
            user_prompt = self._format_single_symbol_prompt(
                state, symbol, run_record, 
                performance=state.performance
            )
            message = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
            
            try:
                if self.llm_with_structure is None:
                    self.llm_with_structure = self._create_llm()
                
                decision = await self.llm_with_structure.ainvoke(message)
                decision.symbol = symbol  # 确保 symbol 正确
                
                # 保存决策到 state
                state.runs[symbol].decision = decision
                logger.info(f"✅ Decision for {symbol}: {decision.action}")
                
            except Exception as e:
                logger.error(f"❌ Decision failed for {symbol}: {e}")
                # 创建默认的 wait 决策
                state.runs[symbol].decision = AIDecision(symbol=symbol, action="wait")
        
        return state
