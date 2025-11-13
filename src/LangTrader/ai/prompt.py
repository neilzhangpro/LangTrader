# 修改 src/LangTrader/ai/prompt.py
from src.LangTrader.utils import logger

class Prompt:
    def __init__(self):
        self.user_prompt = ""
    
    def get_user_prompt(self, state, config, coin_list):
        # 格式化策略信号
        strategy_signals_text = self._format_strategy_signals(state.get("strategy_signals", {}))
        
        user_prompt = f"""
            Market Analysis Data:
            {state["market_data"]}
            -----------------------------
            Current Positions:
            {state.get("position_data", "当前无持仓")}
            -----------------------------
            Historical Performance:
            - Total trades: {state["historical_performance"].get("total_positions", 0)}
            - Winning trades: {state["historical_performance"].get("winning_positions", 0)}
            - Losing trades: {state["historical_performance"].get("losing_positions", 0)}
            - Win rate: {state["historical_performance"].get("win_rate", 0):.1%}
            - Recent 3 times Decisions:
            {state["historical_performance"].get("recent_decisions", "")}
            -----------------------------
            Quantitative Strategy Signals:
            {strategy_signals_text}
            -------------------------------
            Available coins: {coin_list}
            ------------------------------
            Based on the market data, current positions, historical performance, and quantitative strategy signals above:
            1. 如果已有持仓，请评估是否需要加仓、减仓或平仓
            2. 选择最佳的交易币种（如需调整仓位，请对该币种操作）
            3. 仅使用以下编码输出动作与方向：
               - BUY + long  → 开多或增加多头
               - BUY + short → 开空或增加空头
               - SELL + long → 平多或减少多头
               - SELL + short → 平空或减少空头
               - HOLD + none → 保持仓位不变
            4. 特别注意：
                - 如果当前已有持仓，且市场趋势未变，应优先选择 HOLD
                - 不要频繁开平仓，避免不必要的手续费和滑点损失
                - 明确说明当前决策是否基于趋势延续、反转、或风控要求
                - 请参考量化策略信号，但不必完全遵循
            5. 提供置信度 (0.0 到 1.0)
            6. 建议杠杆倍数 (1 到 {config.risk_config.get("max_leverage", 3)})
            7. 超过上限的杠杆将倍数调整为上限，所以请不要输出超过上限的杠杆倍数
            8. 解释决策理由，特别说明对现有仓位的处理，不要超过250字
            9. 如果当前没有持仓，只可以开仓或HOLD,不可以平仓

            如果没有明确交易信号或风险过高，请返回 HOLD，置信度保持较低。
            """
        logger.info(f"User Prompt: {user_prompt}")
        return user_prompt
    
    def _format_strategy_signals(self, strategy_signals):
        """格式化策略信号为文本"""
        if not strategy_signals:
            return "暂无量化策略信号"
        
        formatted_signals = []
        for strategy_name, signal in strategy_signals.items():
            formatted_signals.append(
                f"- {strategy_name}: {signal['action']} (置信度: {signal['confidence']:.2f}, 原因: {signal['reason']})"
            )
        
        return "\n".join(formatted_signals)