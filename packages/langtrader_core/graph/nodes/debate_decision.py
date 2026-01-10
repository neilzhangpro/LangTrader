# packages/langtrader_core/graph/nodes/debate_decision.py
"""
多空辩论决策节点 (Debate Decision Node)

四角色团队进行多空辩论：
1. Analyst - 市场分析师：技术分析，趋势判断
2. Bull - 多头交易员：寻找做多机会
3. Bear - 空头交易员：识别风险，做空机会  
4. RiskManager - 风控经理：仓位审核，风险控制

特点：
- 使用 RunnableParallel 并行调用 Bull 和 Bear
- with_fallbacks 机制处理异常和超时
- 无工具调用，纯推理模式（所有数据来自 state）
- 输出与 batch_decision 兼容的 BatchDecisionResult
"""

from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnableLambda

from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import (
    State,
    BatchDecisionResult,
    PortfolioDecision,
    PerformanceMetrics,
    AnalystOutput,
    TraderSuggestion,
    RiskReview,
    DebateDecisionResult,
)
from datetime import datetime
from langtrader_core.utils import get_logger

import asyncio

logger = get_logger("debate_decision")


# -------------------------
# 默认角色提示词（作为 fallback，优先从文件加载）
# -------------------------

DEFAULT_DEBATE_PROMPTS = {
    "analyst": """你是**市场分析师**，专注于技术分析和趋势判断。

## ⚠️ 重要约束
- **Symbol 格式必须保持原样**：如输入 `BTC/USDC:USDC`，输出也必须是 `BTC/USDC:USDC`，不能简化为 `BTC/USDC`

## 输入数据
你将收到包含以下信息的市场数据：
- K线数据指标（RSI、MACD、布林带等）
- 量化信号得分
- 资金费率

## 你的任务
1. 分析每个币种的技术面
2. 判断趋势方向（bullish/bearish/neutral）
3. 识别关键支撑/阻力位

## 输出格式
为每个币种输出 JSON 格式的分析结果。""",

    "bull": """你是**多头交易员**，专注于寻找做多机会。

## ⚠️ 重要约束
- **Symbol 格式必须保持原样**：如输入 `SOL/USDC:USDC`，输出也必须是 `SOL/USDC:USDC`
- 单币种最大仓位 30%
- 风险回报比至少 2:1
- 只推荐信心度 > 60 的交易

## 止损止盈规则（做多）
- 止损价格 < 当前价格 < 止盈价格
- 示例：当前价格 $1.50 → 止损 $1.40, 止盈 $1.70

## 你的任务
基于分析师的技术分析：
1. 识别上涨信号和做多理由
2. 给出做多建议，包括具体的止损和止盈**价格**（不是百分比）

## 输出格式
为每个看好的币种输出 JSON 建议。""",

    "bear": """你是**空头交易员**，专注于识别风险和做空机会。

## ⚠️ 重要约束
- **Symbol 格式必须保持原样**：如输入 `ETH/USDC:USDC`，输出也必须是 `ETH/USDC:USDC`
- 单币种最大仓位 30%  
- 风险回报比至少 2:1
- 关注资金费率极端情况

## 止损止盈规则（做空）
- 止盈价格 < 当前价格 < 止损价格
- 示例：当前价格 $100 → 止盈 $90, 止损 $105
- **注意**：做空的止损止盈方向与做多相反！

## 你的任务
质疑多头观点，找出：
1. 被忽视的下行风险
2. 技术面的弱点
3. 可能的做空机会，包括具体的止损和止盈**价格**（不是百分比）

## 输出格式
为每个看空或有风险的币种输出 JSON 建议。""",

    "risk_manager": """你是**风控经理**，负责最终审核和仓位协调。

## 🎯 核心目标：提高夏普率
**夏普率（风险调整后收益）是衡量策略好坏的关键指标**。你的每个决策都应考虑：
- 这笔交易能否提高整体夏普率？
- 风险回报比是否 >= 2:1？
- 是否应该减少交易频率，只做高质量交易？

**根据当前夏普率调整策略**：
- 夏普率 < 0：减少交易，只做信心度 > 80 的交易，考虑直接 wait
- 夏普率 0~0.5：保持谨慎，优选高确定性机会
- 夏普率 > 0.5：策略有效，可适度扩大仓位

## 🚨 上轮执行反馈处理
如果市场数据中包含"上轮执行问题"，你**必须**：
1. 分析失败原因（如仓位过大、金额过小、敞口超限）
2. 在本轮决策中主动规避：
   - 总敞口超限 → 降低 allocation_pct 或先平仓
   - 单笔金额过小 → 合并资金到更有信心的币种
   - 杠杆过高 → 降低杠杆倍数

## ⚠️ 重要约束
- **Symbol 格式必须保持原样**：如输入 `PUMP/USDC:USDC`，输出也必须是 `PUMP/USDC:USDC`
- 总仓位上限 80%（考虑已有持仓！）
- 单币种上限 30%
- 最小开仓金额限制（通常 $10）

## 支持的 Action 类型（合约交易）
仅支持以下操作：
- `open_long`: 开多仓
- `open_short`: 开空仓  
- `close_long`: 平多仓（需要有对应持仓）
- `close_short`: 平空仓（需要有对应持仓）
- `wait`: 不操作，观望

注意：不支持 `reduce`（部分减仓）、`hold` 等操作。

## ⚠️ 止损止盈规则（必须遵守！）

止损(stop_loss)和止盈(take_profit)必须是**具体价格**，不是百分比！

**做多(open_long)**：
- 止损价格 < 当前价格 < 止盈价格
- 示例：当前价格 $100 → 止损 $95, 止盈 $110

**做空(open_short)**：
- 止盈价格 < 当前价格 < 止损价格
- 示例：当前价格 $100 → 止盈 $90, 止损 $105

**关键检查**：
- Long: stop_loss < take_profit ✓
- Short: stop_loss > take_profit ✓ （与做多相反！）

## 你的任务
基于多空双方的建议：
1. **检查敞口**：总仓位不超过上限（考虑已有持仓）
2. **检查单币种**：单币种不超过上限
3. **检查止损止盈**：价格方向正确性
4. **参考上轮反馈**：避免重复失败
5. **协调冲突意见**：输出最终决策

## 输出格式
输出最终的投资组合决策，包括：
- symbol: 完整格式（如 `BTC/USDC:USDC`）
- action: open_long/open_short/close_long/close_short/wait
- allocation_pct: 仓位百分比（确保不超限！）
- stop_loss: 止损价格（具体价格，不是百分比）
- take_profit: 止盈价格（具体价格，不是百分比）
- reasoning: 决策理由（包含对上轮问题的回应）""",
}


class DebateDecisionNode(NodePlugin):
    """
    多空辩论决策节点
    
    四阶段流程：
    Phase 1: Analyst 分析市场（串行）
    Phase 2: Bull + Bear 并行分析（abatch）
    Phase 3: RiskManager 审核并输出最终决策（串行）
    
    配置来源（统一从 bots.risk_limits 读取）：
    - 风控约束：max_total_allocation_pct, max_single_allocation_pct 等
    - 节点配置：timeout_per_phase 从 system_configs 读取
    """
    
    metadata = NodeMetadata(
        name="debate_decision",
        display_name="Multi-Role Debate Decision",
        version="1.1.0",
        author="LangTrader official",
        description="四角色多空辩论决策：分析师、多头、空头、风控经理",
        category="decision",
        tags=["decision", "debate", "multi-agent", "official"],
        inputs=["symbols", "market_data"],
        outputs=["batch_decision", "debate_decision"],
        requires=["quant_signal_filter"],
        requires_llm=True,
        insert_after="quant_signal_filter",
        suggested_order=4,
        auto_register=True,  # 模式2启用
    )
    
    # 节点运行时默认配置（非风控配置）
    DEFAULT_NODE_CONFIG = {
        "timeout_per_phase": 120,
    }
    
    # 风控默认配置（仅作为 fallback，优先从 bot.risk_limits 读取）
    DEFAULT_RISK_LIMITS = {
        "max_total_allocation_pct": 80.0,
        "max_single_allocation_pct": 30.0,
        "min_position_size_usd": 10.0,
        "max_position_size_usd": 10000.0,
        "min_risk_reward_ratio": 2.0,
        "max_leverage": 10,
        "default_leverage": 3,
        "max_funding_rate_pct": 0.1,
    }
    
    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        
        if not context:
            raise ValueError("Context not found")
        
        self.llm_factory = context.llm_factory if hasattr(context, 'llm_factory') else None
        self.performance_service = context.performance_service if hasattr(context, 'performance_service') else None
        self.database = context.database if hasattr(context, 'database') else None
        self.bot = context.bot if hasattr(context, 'bot') else None  # 保存 bot 引用用于获取 llm_id
        
        if not self.llm_factory:
            raise ValueError("LLM factory not found in context")
        
        # ========== 统一配置加载 ==========
        # 1. 从 bot.risk_limits 读取风控约束（唯一配置源）
        self.risk_limits = {}
        if self.bot:
            self.risk_limits = self.bot.risk_limits or {}
            logger.debug(f"Loaded risk_limits from bot: {list(self.risk_limits.keys())}")
        
        # 2. 从 system_configs 读取节点配置
        db_config = self.load_config_from_database('debate_decision')
        
        # 3. 合并配置：bot.risk_limits > system_configs > 默认值
        self.node_config = {
            # 风控约束（从 risk_limits 读取，统一使用百分比格式）
            "max_total_allocation_pct": self.risk_limits.get('max_total_allocation_pct', self.DEFAULT_RISK_LIMITS['max_total_allocation_pct']),
            "max_single_allocation_pct": self.risk_limits.get('max_single_allocation_pct', self.DEFAULT_RISK_LIMITS['max_single_allocation_pct']),
            "min_position_size_usd": self.risk_limits.get('min_position_size_usd', self.DEFAULT_RISK_LIMITS['min_position_size_usd']),
            "max_position_size_usd": self.risk_limits.get('max_position_size_usd', self.DEFAULT_RISK_LIMITS['max_position_size_usd']),
            "min_risk_reward_ratio": self.risk_limits.get('min_risk_reward_ratio', self.DEFAULT_RISK_LIMITS['min_risk_reward_ratio']),
            "max_leverage": self.risk_limits.get('max_leverage', self.DEFAULT_RISK_LIMITS['max_leverage']),
            "default_leverage": self.risk_limits.get('default_leverage', self.DEFAULT_RISK_LIMITS['default_leverage']),
            "max_funding_rate_pct": self.risk_limits.get('max_funding_rate_pct', self.DEFAULT_RISK_LIMITS['max_funding_rate_pct']),
            
            # 节点配置（从 system_configs 读取）
            "timeout_per_phase": db_config.get('debate_decision.timeout_per_phase', self.DEFAULT_NODE_CONFIG['timeout_per_phase']),
        }
        
        # 覆盖传入的 config
        if config:
            self.node_config.update(config)
        # 加载角色 LLM ID
        role_llm_ids = None
        # 优先从传入的config参数读取
        if config and 'role_llm_ids' in config:
            role_llm_ids = config.get('role_llm_ids', {})
            logger.info(f"Loaded role_llm_ids from config: {role_llm_ids}")
        self.role_llm_ids = role_llm_ids
        self._role_llms ={} # 用来缓存角色LLM实例
        self._llm = None
        
        # 加载角色提示词（从文件，fallback 到默认值）
        self.debate_prompts = self._load_debate_prompts()
        
        logger.info(f"✅ DebateDecisionNode initialized with risk_limits from bot")
        logger.info(f"   max_total={self.node_config['max_total_allocation_pct']}%, max_single={self.node_config['max_single_allocation_pct']}%")
    
    def _load_debate_prompts(self) -> Dict[str, str]:
        """
        加载辩论角色提示词
        
        从 prompts/ 文件夹加载 4 个角色的提示词文件：
        - debate_analyst.txt
        - debate_bull.txt
        - debate_bear.txt
        - debate_risk_manager.txt
        
        如果文件不存在，使用默认提示词作为 fallback
        
        Returns:
            Dict[str, str]: 角色名 -> 提示词内容
        """
        current_dir = Path(__file__).parent
        prompts_dir = current_dir.parent.parent / "prompts"
        
        prompts = {}
        roles = ["analyst", "bull", "bear", "risk_manager"]
        
        for role in roles:
            file_path = prompts_dir / f"debate_{role}.txt"
            if file_path.exists():
                prompts[role] = file_path.read_text(encoding="utf-8")
                logger.debug(f"📝 Loaded prompt for {role}: {len(prompts[role])} chars")
            else:
                logger.warning(f"⚠️ Prompt file not found: {file_path}, using default")
                prompts[role] = DEFAULT_DEBATE_PROMPTS.get(role, "")
        
        return prompts
    
    def _get_llm(self,role:Optional[str]=None):
        """
        获取 LLM 实例
        
        优先级：bot.llm_id > default LLM
        """
        # update: 这里是主LLM，不是角色LLM
        if self._llm is None:
            # 优先使用 bot 配置的 LLM
            if self.bot and hasattr(self.bot, 'llm_id') and self.bot.llm_id:
                logger.info(f"Using bot-specific LLM: llm_id={self.bot.llm_id}")
                self._llm = self.llm_factory.create_from_id(self.bot.llm_id)
            else:
                # 否则使用默认 LLM
                logger.info("Using default LLM")
                self._llm = self.llm_factory.create_default()
        # 配置角色LLM,如果配置中role_llm_ids为空，则不执行，默认使用主LLM
        # 如果配置项对不上，则不执行，默认使用主LLM
        if self.role_llm_ids and role:
            for jiaose, llm_id in self.role_llm_ids.items():
                if jiaose not in self._role_llms:
                    self._role_llms[jiaose] = self.llm_factory.create_from_id(llm_id)
            if role in self._role_llms:
                return self._role_llms[role]
        return self._llm
    
    def _build_market_context(self, state: State) -> str:
        """
        构建市场数据上下文
        
        包含：
        - 绩效反馈（让 AI 根据历史表现调整策略）
        - 风控约束（让 AI 提前知道这些限制）
        - 账户状态
        - 当前持仓
        - 候选币种数据
        """
        context = "# 市场数据\n\n"
        
        # ========== 绩效反馈（如果有） ==========
        if state.performance and state.performance.total_trades > 0:
            context += state.performance.to_prompt_text()
            context += "\n"
        
        # ========== 上轮执行问题（如果有） ==========
        if state.alerts:
            context += "## 🚨 上轮执行问题（需重点关注）\n"
            for alert in state.alerts:
                context += f"- {alert}\n"
            context += "\n**请在本轮决策中避免重复以上错误，调整仓位分配或等待更好时机**\n\n"
        
        # ========== 风控约束（AI 决策前必须知道） ==========
        context += "## ⚠️ 风控约束（必须遵守）\n"
        context += f"- 总仓位上限: {self.node_config['max_total_allocation_pct']:.0f}%\n"
        context += f"- 单币种上限: {self.node_config['max_single_allocation_pct']:.0f}%\n"
        context += f"- 最小开仓金额: ${self.node_config['min_position_size_usd']:.0f}\n"
        context += f"- 最大开仓金额: ${self.node_config['max_position_size_usd']:.0f}\n"
        context += f"- 最小风险回报比: {self.node_config['min_risk_reward_ratio']:.1f}:1\n"
        context += f"- 最大杠杆: {self.node_config['max_leverage']}x\n"
        context += f"- 推荐杠杆: {self.node_config['default_leverage']}x\n"
        context += f"- 资金费率上限: {self.node_config['max_funding_rate_pct']:.2f}%（超过则不开仓）\n"
        context += "\n"
        
        # ========== 账户状态 ==========
        # 计算已用保证金（考虑杠杆）
        used_margin = 0.0
        if state.positions:
            used_margin = sum(pos.margin_used for pos in state.positions)
        
        if state.account:
            total_balance = state.account.total.get('USDT', 0) or state.account.total.get('USDC', 0)
            free_balance = state.account.free.get('USDT', 0) or state.account.free.get('USDC', 0)
            context += f"## 账户\n"
            context += f"- 总资产: ${total_balance:.2f}（包含持仓锁定）\n"
            context += f"- **可用余额: ${free_balance:.2f}** ⚠️ 分配仓位时必须基于此值计算\n"
            context += f"- 已用保证金: ${used_margin:.2f}\n"
            
            # 计算可用于新开仓的金额（总额度 - 已用保证金）
            max_total_margin = free_balance * (self.node_config['max_total_allocation_pct'] / 100)
            available_margin = max(0, max_total_margin - used_margin)
            margin_usage_pct = (used_margin / max_total_margin * 100) if max_total_margin > 0 else 0
            context += f"- 可开仓额度: ${available_margin:.2f}（已用 {margin_usage_pct:.1f}%）\n"
            
            # 计算示例，帮助 AI 正确理解
            min_alloc_for_10usd = (10.0 / free_balance * 100) if free_balance > 0 else 100
            context += f"\n💡 **allocation_pct 计算基准**: 可用余额 ${free_balance:.2f}\n"
            context += f"   例如：开 $10 仓位 → allocation_pct = {min_alloc_for_10usd:.1f}%\n\n"
        
        # ========== 当前持仓（优先评估是否需要平仓！） ==========
        if state.positions:
            context += "## 🔔 当前持仓（优先评估是否需要平仓！）\n"
            context += "**重要**：请先检查以下持仓是否需要平仓（止盈/止损/趋势反转），再考虑新开仓！\n\n"
            
            for pos in state.positions:
                # 获取该币种的当前价格
                market_data = state.market_data.get(pos.symbol, {})
                indicators = market_data.get('indicators', {})
                current_price = indicators.get('current_price', pos.price)
                
                # 计算未实现盈亏
                if pos.side == 'buy':
                    # 多头：(现价 - 入场价) / 入场价
                    pnl_pct = ((current_price - pos.price) / pos.price * 100) if pos.price > 0 else 0
                else:
                    # 空头：(入场价 - 现价) / 入场价
                    pnl_pct = ((pos.price - current_price) / pos.price * 100) if pos.price > 0 else 0
                
                # 盈亏状态标识和操作建议
                # 新逻辑：趋势持续时不急于平仓，让利润奔跑
                if pnl_pct >= 10:
                    pnl_emoji = "🎯 **可考虑止盈**"
                    action_hint = "盈利丰厚，可根据趋势决定是否止盈"
                elif pnl_pct >= 5:
                    pnl_emoji = "📈 盈利良好"
                    action_hint = "趋势持续则继续持有，趋势减弱可止盈"
                elif pnl_pct > 0:
                    pnl_emoji = "🟢 盈利中"
                    action_hint = "趋势持续则继续持有"
                elif pnl_pct > -3:
                    pnl_emoji = "🔴 轻微亏损"
                    action_hint = "观察趋势，必要时止损"
                else:
                    pnl_emoji = "🛑 **必须止损**"
                    action_hint = "亏损超3%，必须立即止损！"
                
                # 显示详细信息
                side_cn = "多头" if pos.side == 'buy' else "空头"
                context += f"### {pos.symbol} ({side_cn})\n"
                context += f"- 入场价: ${pos.price:.4f}\n"
                context += f"- 当前价: ${current_price:.4f}\n"
                context += f"- **未实现盈亏: {pnl_pct:+.2f}%** {pnl_emoji}\n"
                context += f"- 数量: {pos.amount:.6f}, 杠杆: {pos.leverage}x, 保证金: ${pos.margin_used:.2f}\n"
                context += f"- 💡 建议: {action_hint}\n"
                
                # 只有亏损超过3%时才强烈建议平仓
                if pnl_pct <= -3:
                    close_action = "close_long" if pos.side == 'buy' else "close_short"
                    context += f"- ⚡ **强制操作: `{close_action}` 止损离场**\n"
                
                context += "\n"
        else:
            context += "## 当前持仓\n无持仓，可考虑新开仓。\n\n"
        
        # ========== 候选币种 ==========
        context += "## 候选币种\n\n"
        for symbol in state.symbols:
            context += f"### {symbol}\n"
            
            market_data = state.market_data.get(symbol, {})
            indicators = market_data.get('indicators', {})
            
            # 当前价格
            current_price = indicators.get('current_price', 0)
            if current_price:
                context += f"- 当前价格: ${current_price:.4f}\n"
            
            # 量化信号
            quant_signal = indicators.get('quant_signal', {})
            if quant_signal:
                context += f"- 量化得分: {quant_signal.get('total_score', 'N/A')}/100\n"
                breakdown = quant_signal.get('breakdown', {})
                context += f"  - 趋势: {breakdown.get('trend', 0)}, 动量: {breakdown.get('momentum', 0)}\n"
                context += f"  - 量能: {breakdown.get('volume', 0)}, 情绪: {breakdown.get('sentiment', 0)}\n"
            
            # RSI/MACD 等
            rsi = indicators.get('rsi_14', 0)
            macd = indicators.get('macd', {})
            if rsi:
                context += f"- RSI(14): {rsi:.2f}\n"
            if macd:
                context += f"- MACD: {macd.get('macd', 0):.4f}, Signal: {macd.get('signal', 0):.4f}\n"
            
            # 资金费率
            funding_rate = indicators.get('funding_rate', 0)
            if funding_rate is not None:
                context += f"- 资金费率: {funding_rate*100:.4f}%"
                # 资金费率风险提示
                max_rate = self.node_config['max_funding_rate_pct']
                if abs(funding_rate * 100) > max_rate:
                    context += f" ⚠️ 超过上限{max_rate}%"
                context += "\n"
            
            context += "\n"
        
        return context
    
    async def _run_analyst(self, market_context: str) -> List[AnalystOutput]:
        """
        Phase 1: 市场分析师分析
        
        使用 with_fallbacks 机制处理异常
        """
        logger.info("📊 Phase 1: Analyst 分析市场...")
        
        llm = self._get_llm(role="analyst").with_structured_output(AnalystOutput)
        timeout = self.node_config['timeout_per_phase']
        
        # 创建 fallback（返回中性分析）
        async def analyst_fallback(messages):
            logger.warning("⚠️ Analyst 使用 fallback - 返回中性分析")
            return AnalystOutput(
                symbol="FALLBACK",     # 必填字段
                trend="neutral",
                key_levels=None,       # 类型应为 Optional[Dict]，不是 List
                summary="分析失败，默认中性判断"
            )
        
        # 带 fallback 的 chain
        safe_llm = llm.with_fallbacks(
            [RunnableLambda(analyst_fallback)],
            exceptions_to_handle=(Exception,)
        )
        
        messages = [
            SystemMessage(content=self.debate_prompts["analyst"]),
            HumanMessage(content=f"请分析以下市场数据：\n\n{market_context}"),
        ]
        
        try:
            result = await asyncio.wait_for(
                safe_llm.ainvoke(messages),
                timeout=timeout
            )
            logger.info(f"✅ Analyst 完成: {result.trend}")
            return [result] if isinstance(result, AnalystOutput) else result
        except asyncio.TimeoutError:
            logger.error(f"❌ Analyst 超时 ({timeout}s) - 使用默认中性分析")
            return [AnalystOutput(
                symbol="TIMEOUT",      # 必填字段
                trend="neutral", 
                key_levels=None,       # 类型应为 Optional[Dict]，不是 List
                summary="分析超时，默认中性"
            )]
        except Exception as e:
            logger.error(f"❌ Analyst 失败: {e}")
            # 返回 fallback 结果而非空列表，避免后续处理失败
            return [AnalystOutput(
                symbol="ERROR",
                trend="neutral",
                key_levels=None,
                summary=f"分析出错: {str(e)[:50]}"
            )]
    
    async def _run_phase2_parallel(
        self, 
        market_context: str, 
        analyst_summary: str
    ) -> Tuple[List[TraderSuggestion], List[TraderSuggestion]]:
        """
        Phase 2: Bull 和 Bear 并行分析
        
        使用 RunnableParallel + with_fallbacks 实现并行调用
        """
        logger.info("📊 Phase 2: Bull + Bear 并行分析...")
        
        llm_bull = self._get_llm(role="bull")
        llm_bear = self._get_llm(role="bear")
        timeout = self.node_config.get("timeout_per_phase", 120)
        
        # 构建 Bull 和 Bear 的 Chain
        bull_prompt = ChatPromptTemplate.from_messages([
            ("system", self.debate_prompts["bull"]),
            ("human", "分析师总结:\n{analyst}\n\n市场数据:\n{context}\n\n请给出做多建议。"),
        ])
        
        bear_prompt = ChatPromptTemplate.from_messages([
            ("system", self.debate_prompts["bear"]),
            ("human", "分析师总结:\n{analyst}\n\n市场数据:\n{context}\n\n请给出风险分析和做空建议。"),
        ])
        
        # 使用结构化输出
        bull_chain = bull_prompt | llm_bull.with_structured_output(TraderSuggestion)
        bear_chain = bear_prompt | llm_bear.with_structured_output(TraderSuggestion)
        
        # 创建 fallback 函数（返回 None 表示该角色失败）
        def create_fallback(role: str):
            """创建返回 None 的 fallback，便于下游处理"""
            async def fallback_fn(input_data):
                logger.warning(f"⚠️ {role} 使用 fallback - 返回空建议")
                return None
            return RunnableLambda(fallback_fn)
        
        # 添加 fallback 保护
        bull_chain_safe = bull_chain.with_fallbacks(
            [create_fallback("Bull")],
            exceptions_to_handle=(Exception,)
        )
        bear_chain_safe = bear_chain.with_fallbacks(
            [create_fallback("Bear")],
            exceptions_to_handle=(Exception,)
        )
        
        # 使用 RunnableParallel 并行执行
        parallel_chain = RunnableParallel(bull=bull_chain_safe, bear=bear_chain_safe)
        
        # 准备输入
        input_data = {"analyst": analyst_summary, "context": market_context}
        
        try:
            # 使用 asyncio.wait_for 处理整体超时
            result = await asyncio.wait_for(
                parallel_chain.ainvoke(input_data),
                timeout=timeout
            )
            
            bull_result = result.get("bull")
            bear_result = result.get("bear")
            
            # 统计结果
            bull_ok = bull_result is not None
            bear_ok = bear_result is not None
            
            logger.info(f"✅ Phase 2 完成: Bull={'OK' if bull_ok else 'FAIL'}, Bear={'OK' if bear_ok else 'FAIL'}")
            
            # 返回列表以保持下游兼容
            bull_list = [bull_result] if bull_result else []
            bear_list = [bear_result] if bear_result else []
            return (bull_list, bear_list)
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Phase 2 整体超时 ({timeout}s)")
            return ([], [])
        except Exception as e:
            logger.error(f"❌ Phase 2 失败: {e}")
            return ([], [])
    
    async def _run_risk_manager(
        self,
        state: State,
        market_context: str,
        bull_suggestions: List[TraderSuggestion],
        bear_suggestions: List[TraderSuggestion],
    ) -> BatchDecisionResult:
        """
        Phase 3: 风控经理审核并输出最终决策
        
        使用 with_fallbacks 机制处理异常
        """
        logger.info("📊 Phase 3: RiskManager 审核...")
        
        llm = self._get_llm(role="risk_manager")
        timeout = self.node_config['timeout_per_phase']
        
        # 构建审核输入
        review_input = f"""# 辩论结果汇总

## 市场数据
{market_context}

## 多头建议
"""
        for s in bull_suggestions:
            review_input += f"- {s.symbol}: {s.action}, 仓位{s.allocation_pct}%, 信心{s.confidence}\n"
            review_input += f"  理由: {s.reasoning}\n"

        review_input += "\n## 空头建议\n"
        for s in bear_suggestions:
            review_input += f"- {s.symbol}: {s.action}, 仓位{s.allocation_pct}%, 信心{s.confidence}\n"
            review_input += f"  理由: {s.reasoning}\n"

        review_input += f"""
## 约束条件
- 总仓位上限: {self.node_config['max_total_allocation_pct']}%
- 单币种上限: {self.node_config['max_single_allocation_pct']}%
- 必须输出每个候选币种的最终决策

## 候选币种列表（必须使用完整格式）
{state.symbols}

请输出最终的投资组合决策，symbol 必须使用上述完整格式。
"""
        
        messages = [
            SystemMessage(content=self.debate_prompts["risk_manager"]),
            HumanMessage(content=review_input),
        ]
        
        # 创建 fallback（返回默认决策）
        # 注意：使用闭包捕获 state
        default_decisions = self._create_default_decisions(state)
        
        async def risk_manager_fallback(msgs):
            logger.warning("⚠️ RiskManager 使用 fallback - 返回默认 wait 决策")
            return default_decisions
        
        try:
            # 直接输出 BatchDecisionResult
            llm_structured = llm.with_structured_output(BatchDecisionResult)
            
            # 带 fallback 的 chain
            safe_llm = llm_structured.with_fallbacks(
                [RunnableLambda(risk_manager_fallback)],
                exceptions_to_handle=(Exception,)
            )
            
            result = await asyncio.wait_for(
                safe_llm.ainvoke(messages),
                timeout=timeout
            )
            
            logger.info(f"✅ RiskManager 完成: {len(result.decisions)} 个决策")
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"❌ RiskManager 超时 ({timeout}s) - 使用默认决策")
            return default_decisions
        except Exception as e:
            logger.error(f"❌ RiskManager 失败: {e}")
            return default_decisions
    
    def _create_default_decisions(self, state: State) -> BatchDecisionResult:
        """创建默认的 wait 决策"""
        decisions = []
        for symbol in state.symbols:  # 使用 symbols 而非 runs
            decisions.append(PortfolioDecision(
                symbol=symbol,
                action="wait",
                allocation_pct=0,
                confidence=0,
                reasoning="辩论流程异常，默认观望"
            ))
        return BatchDecisionResult(
            decisions=decisions,
            total_allocation_pct=0,
            cash_reserve_pct=100,
            strategy_rationale="辩论流程异常，全部观望"
        )
    
    def _normalize_allocations(self, result: BatchDecisionResult) -> BatchDecisionResult:
        """规范化仓位分配"""
        max_total = self.node_config['max_total_allocation_pct']
        max_single = self.node_config['max_single_allocation_pct']
        
        # 检查单币种限制
        for d in result.decisions:
            if d.allocation_pct > max_single:
                logger.warning(f"⚠️ {d.symbol}: {d.allocation_pct}% > max {max_single}%")
                d.allocation_pct = max_single
        
        # 检查总仓位限制
        total = sum(d.allocation_pct for d in result.decisions if d.action not in ("wait", "hold"))
        
        if total > max_total:
            scale = max_total / total
            logger.warning(f"⚠️ 总仓位 {total:.1f}% > {max_total}%, 缩放 {scale:.2f}")
            for d in result.decisions:
                if d.action not in ("wait", "hold"):
                    d.allocation_pct *= scale
        
        # 更新汇总
        result.total_allocation_pct = sum(
            d.allocation_pct for d in result.decisions if d.action not in ("wait", "hold")
        )
        result.cash_reserve_pct = 100 - result.total_allocation_pct
        
        return result
    
    async def run(self, state: State) -> State:
        """
        执行多空辩论决策
        
        流程:
        1. Analyst 分析市场
        2. Bull + Bear 并行辩论 (abatch)
        3. RiskManager 审核输出
        """
        logger.info("=" * 60)
        logger.info("🎭 DebateDecision 开始")
        logger.info(f"   候选币种: {state.symbols}")  # 修复：使用 symbols 而非 runs
        logger.info("=" * 60)
        
        # 加载绩效
        if self.performance_service:
            try:
                perf = self.performance_service.calculate_metrics(state.bot_id)
                state.performance = PerformanceMetrics(
                    total_trades=perf.total_trades,
                    winning_trades=perf.winning_trades,
                    losing_trades=perf.losing_trades,
                    win_rate=perf.win_rate,
                    sharpe_ratio=perf.sharpe_ratio,
                    max_drawdown=perf.max_drawdown,
                )
                logger.info(f"📊 绩效: sharpe={perf.sharpe_ratio:.2f}")
            except Exception as e:
                logger.warning(f"⚠️ 绩效加载失败: {e}")
        
        # 构建市场上下文
        market_context = self._build_market_context(state)
        
        # Phase 1: Analyst
        analyst_outputs = await self._run_analyst(market_context)
        analyst_summary = "\n".join([
            f"{a.symbol}: {a.trend}, {a.summary}" 
            for a in analyst_outputs
        ]) if analyst_outputs else "分析师未提供分析"
        
        # Phase 2: Bull + Bear 并行
        bull_suggestions, bear_suggestions = await self._run_phase2_parallel(
            market_context, analyst_summary
        )
        
        # Phase 3: RiskManager
        batch_result = await self._run_risk_manager(
            state, market_context, bull_suggestions, bear_suggestions
        )
        
        # 规范化仓位
        batch_result = self._normalize_allocations(batch_result)
        
        # -------------------------
        # 保存辩论过程到 state.debate_decision
        # -------------------------
        debate_summary = f"Analyst: {len(analyst_outputs)} reports, Bull: {len(bull_suggestions)} suggestions, Bear: {len(bear_suggestions)} suggestions"
        
        state.debate_decision = DebateDecisionResult(
            analyst_outputs=analyst_outputs,
            bull_suggestions=bull_suggestions,
            bear_suggestions=bear_suggestions,
            final_decision=batch_result,
            debate_summary=debate_summary,
            completed_at=datetime.now(),
        )
        
        # 同时保存到 batch_decision（与 execution 兼容）
        state.batch_decision = batch_result
        
        logger.info("=" * 60)
        logger.info(f"🎭 DebateDecision 完成")
        logger.info(f"   总仓位: {batch_result.total_allocation_pct:.1f}%")
        logger.info(f"   决策: {[f'{d.symbol}:{d.action}' for d in batch_result.decisions]}")
        logger.info("=" * 60)
        
        # 清空 alerts（已读取并注入到本轮决策上下文）
        state.alerts = []
        
        return state

