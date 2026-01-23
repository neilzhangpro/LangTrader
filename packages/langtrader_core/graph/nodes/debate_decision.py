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
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel, RunnableLambda

from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import (
    State,
    BatchDecisionResult,
    PortfolioDecision,
    PerformanceMetrics,
    AnalystOutput,
    AnalystOutputList,
    TraderSuggestion,
    DebateRound,
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
    "analyst": """你是**市场分析师**，专注于深入分析市场数据和技术指标。

## 🎯 核心职责
你的唯一职责是**提供客观、全面的市场分析**，为后续的交易决策提供数据支撑。
- 专注于技术分析和趋势判断
- 识别关键支撑位和阻力位
- 评估市场情绪和技术信号强度
- **不进行交易建议**，只提供分析结论

## ⚠️ 重要约束
- **Symbol 格式必须保持原样**：如输入 `BTC/USDC:USDC`，输出也必须是 `BTC/USDC:USDC`，不能简化为 `BTC/USDC`

## 输入数据
你将收到包含以下信息的市场数据：
- K线数据指标（RSI、MACD、布林带等）
- 量化信号得分
- 资金费率

## 你的任务
1. **深度技术分析**：全面分析每个币种的技术指标和形态
2. **趋势判断**：准确判断趋势方向（bullish/bearish/neutral）及其强度
3. **关键位识别**：识别重要的支撑位和阻力位
4. **综合分析**：将多个指标综合起来，给出全面的市场观点

## 输出格式
为每个币种输出 JSON 格式的分析结果，包含趋势判断、关键位和详细分析摘要。""",

    "bull": """你是**多头交易员**，专注于从候选币种和分析数据中，寻找**最大胜率的做多机会**。

## 🎯 核心职责
你的唯一目标是**识别并推荐具有最高胜率的做多交易机会**。
- 深度分析候选币种，筛选最具潜力的做多标的
- 结合市场分析师的技术分析，寻找被低估的上涨机会
- 严格评估每个机会的胜率和风险回报比
- 只推荐高确定性的做多机会，放弃低质量信号

## ⚠️ 重要约束
- **Symbol 格式必须保持原样**：如输入 `SOL/USDC:USDC`，输出也必须是 `SOL/USDC:USDC`
- 单币种最大仓位 30%
- 风险回报比至少 2:1
- **推荐信心度 > 50 的交易机会**（不要过于保守，有一定把握就可以推荐）

## 止损止盈规则（做多）
- 止损价格 < 当前价格 < 止盈价格
- 示例：当前价格 $1.50 → 止损 $1.40, 止盈 $1.70

## 你的任务
基于候选币种列表和分析师的技术分析：
1. **筛选最佳做多标的**：从所有候选币种中，识别具有最高胜率的做多机会
2. **深度评估胜率**：综合考虑技术面、量化信号、市场情绪等因素，评估每个机会的胜率
3. **寻找最强信号**：优先选择技术面强、量化得分高、趋势明确的币种
4. **给出精准建议**：为高胜率机会提供具体的止损和止盈**价格**（不是百分比）和仓位建议

## 输出格式
为候选币种输出 JSON 建议。如果有交易机会（信心度 > 50），积极推荐；如果确实没有机会，action 设为 wait。""",

    "bear": """你是**空头交易员**，专注于从候选币种和分析数据中，寻找**最大胜率的做空机会**。

## 🎯 核心职责
你的唯一目标是**识别并推荐具有最高胜率的做空交易机会**。
- 深度分析候选币种，筛选最具潜力的做空标的
- 结合市场分析师的技术分析，寻找被高估的下行风险
- 严格评估每个机会的胜率和风险回报比
- 只推荐高确定性的做空机会，放弃低质量信号

## ⚠️ 重要约束
- **Symbol 格式必须保持原样**：如输入 `ETH/USDC:USDC`，输出也必须是 `ETH/USDC:USDC`
- 单币种最大仓位 30%  
- 风险回报比至少 2:1
- **推荐信心度 > 50 的交易机会**（不要过于保守，有一定把握就可以推荐）
- 关注资金费率极端情况（高资金费率可能预示下跌）

## ⚠️ 止损止盈规则（做空）- 极其重要！
**做空的止损止盈方向与做多完全相反！**

正确格式：`止盈价格 < 当前价格 < 止损价格`
- 示例：当前价格 $100 → 止盈 $90（在下方），止损 $105（在上方）
- 止盈 (take_profit) = 期望价格下跌到的目标位
- 止损 (stop_loss) = 如果价格上涨到此处则止损

**验证规则**：做空时必须满足 `stop_loss > take_profit`
- ✅ 正确：SL=105, TP=90 (105 > 90)
- ❌ 错误：SL=95, TP=110 (这是做多的设置！会被系统拒绝)

## 你的任务
基于候选币种列表和分析师的技术分析：
1. **筛选最佳做空标的**：从所有候选币种中，识别具有最高胜率的做空机会
2. **识别下行信号**：寻找技术面转弱、量化信号负面、趋势反转的币种
3. **深度评估胜率**：综合考虑技术面弱点、资金费率、市场情绪等因素，评估做空机会的胜率
4. **质疑多头观点**：找出被忽视的下行风险和潜在的技术面弱点
5. **给出精准建议**：为高胜率做空机会提供具体的止损和止盈**价格**（不是百分比）和仓位建议

## 输出格式
为候选币种输出 JSON 建议。如果有交易机会（信心度 > 50），积极推荐；如果确实没有机会，action 设为 wait。""",

    "risk_manager": """你是**风险经理**，专注于**评估交易风险并做出平衡决策**。

## 🎯 核心职责
你的主要职责是**在风险可控的前提下促成交易**：
- 评估每笔交易的风险是否在可接受范围内
- 确保整体投资组合的风险敞口符合要求
- 识别并量化潜在风险因素
- **平衡原则**：在风险可控时积极采纳 Bull/Bear 的建议，只有风险明显过高时才拒绝

## 🔍 风险识别重点
在评估多空双方建议时，重点关注以下风险：

### 1. 仓位风险
- 总仓位是否超限（考虑已有持仓）
- 单币种仓位是否集中度过高
- 是否违反了仓位分散原则

### 2. 价格风险
- 止损止盈价格设置是否合理
- 风险回报比是否达到要求（至少 2:1）
- 当前价格与止损止盈的相对位置是否正确

### 3. 市场风险
- 资金费率是否异常（过高可能预示反转）
- 技术面是否存在反转信号
- 市场情绪是否过度乐观/悲观

### 4. 执行风险
- 是否满足最小开仓金额要求
- 杠杆倍数是否合理
- 是否有足够的可用余额

### 5. 历史风险
- 上轮执行是否存在问题（必须规避重复错误）
- 当前绩效是否表明策略需要调整
- 连续亏损是否需要暂停交易

## 🎯 核心目标：平衡收益与风险
你的目标是在**风险可控的前提下积极寻找交易机会**，而不是过度保守导致错失良机。

**决策原则**：
- 风险回报比 >= 2:1 的交易值得尝试
- 信心度 > 55 且技术面支持的交易可以执行
- 新策略阶段需要交易数据来验证，**不要过度保守**

**根据历史表现调整仓位**（参考绩效建议）：
- 新 bot（无历史交易）：正常交易，小仓位（10-15%）试探
- 夏普率 < 0：降低仓位至 15%，但不要停止交易
- 夏普率 0~0.5：正常仓位，信心度 > 55 即可
- 夏普率 > 0.5：可以增加仓位

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
- `wait`: 不操作，观望（当风险过高时优先选择）

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
基于多空双方的建议和市场数据：
1. **评估交易机会**：优先考虑 Bull/Bear 中信心度更高的建议
2. **检查仓位风险**：确保总仓位和单币种仓位符合限制
3. **检查价格风险**：验证止损止盈设置的合理性和正确性
4. **检查执行风险**：确保满足最小金额、杠杆等要求
5. **处理历史风险**：参考上轮执行反馈，避免重复错误
6. **积极决策**：如果 Bull 或 Bear 给出了信心度 > 55 且风险可控的建议，**应该采纳**而非 wait
7. **输出最终决策**：在多空建议中择优选择，只有在双方都没有好机会时才 wait

## 输出格式
输出最终的投资组合决策，包括：
- symbol: 完整格式（如 `BTC/USDC:USDC`）
- action: open_long/open_short/close_long/close_short/wait
- allocation_pct: 仓位百分比（确保不超限！）
- stop_loss: 止损价格（具体价格，不是百分比）
- take_profit: 止盈价格（具体价格，不是百分比）
- reasoning: 决策理由（重点说明风险识别和评估过程，包含对上轮问题的回应）""",
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
        suggested_order=5,
        auto_register=True,  # 模式2启用
    )
    
    # 节点运行时默认配置（非风控配置）
    DEFAULT_NODE_CONFIG = {
        "timeout_per_phase": 120,
        "debate_max_rounds": 2,  # 辩论轮数（从 system_configs 的 debate.max_rounds 读取）
        "trade_history_limit": 10,  # 注入的交易历史条数
    }
    
    # 风控默认配置（仅作为 fallback，优先从 bot.risk_limits 读取）
    # 注意：百分比使用整数格式（80 = 80%），用于 AI prompt 展示
    DEFAULT_RISK_LIMITS = {
        "max_total_allocation_pct": 80.0,
        "max_single_allocation_pct": 30.0,
        "min_position_size_usd": 10.0,
        "max_position_size_usd": 5000.0,
        "min_risk_reward_ratio": 2.0,
        "max_leverage": 5,
        "default_leverage": 3,
        "max_funding_rate_pct": 0.05,  # 0.05%，正常市场资金费率范围
    }
    
    def _get_allocation_pct(self, risk_limits: dict, key: str, default: float) -> float:
        """
        兼容读取仓位百分比配置
        
        支持两种字段名格式：
        - 旧格式：max_total_allocation_pct (整数，80 = 80%)
        - 新格式：max_total_exposure_pct (小数，0.8 = 80%)
        
        返回整数格式的百分比（用于 AI prompt）
        """
        # 字段名映射（新名称 -> 旧名称）
        name_map = {
            'max_total_allocation_pct': 'max_total_exposure_pct',
            'max_single_allocation_pct': 'max_single_symbol_pct',
        }
        
        # 1. 优先尝试新字段名（小数格式）
        new_key = name_map.get(key)
        if new_key and new_key in risk_limits:
            value = risk_limits[new_key]
            # 小数格式转换为整数百分比（0.8 -> 80）
            if value <= 1:
                return value * 100
            return value
        
        # 2. 尝试旧字段名（整数格式）
        if key in risk_limits:
            value = risk_limits[key]
            # 如果是小数格式，转换为整数百分比
            if value <= 1:
                return value * 100
            return value
        
        # 3. 返回默认值
        return default
    
    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        
        if not context:
            raise ValueError("Context not found")
        
        self.llm_factory = context.llm_factory if hasattr(context, 'llm_factory') else None
        self.performance_service = context.performance_service if hasattr(context, 'performance_service') else None
        self.database = context.database if hasattr(context, 'database') else None
        self.bot = context.bot if hasattr(context, 'bot') else None  # 保存 bot 引用用于获取 llm_id
        self.trade_history_repo = context.trade_history_repo if hasattr(context, 'trade_history_repo') else None
        
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
            # 风控约束（从 risk_limits 读取，统一使用百分比格式 80 = 80%）
            # 使用兼容方法，支持新旧两种字段名和格式
            "max_total_allocation_pct": self._get_allocation_pct(self.risk_limits, 'max_total_allocation_pct', self.DEFAULT_RISK_LIMITS['max_total_allocation_pct']),
            "max_single_allocation_pct": self._get_allocation_pct(self.risk_limits, 'max_single_allocation_pct', self.DEFAULT_RISK_LIMITS['max_single_allocation_pct']),
            "min_position_size_usd": self.risk_limits.get('min_position_size_usd', self.DEFAULT_RISK_LIMITS['min_position_size_usd']),
            "max_position_size_usd": self.risk_limits.get('max_position_size_usd', self.DEFAULT_RISK_LIMITS['max_position_size_usd']),
            "min_risk_reward_ratio": self.risk_limits.get('min_risk_reward_ratio', self.DEFAULT_RISK_LIMITS['min_risk_reward_ratio']),
            "max_leverage": self.risk_limits.get('max_leverage', self.DEFAULT_RISK_LIMITS['max_leverage']),
            "default_leverage": self.risk_limits.get('default_leverage', self.DEFAULT_RISK_LIMITS['default_leverage']),
            "max_funding_rate_pct": self.risk_limits.get('max_funding_rate_pct', self.DEFAULT_RISK_LIMITS['max_funding_rate_pct']),
            
            # 节点配置（从 system_configs 读取）
            "debate_enabled": db_config.get('debate.enabled', True),  # 是否启用辩论机制
            "timeout_per_phase": db_config.get('debate.timeout_per_phase', self.DEFAULT_NODE_CONFIG['timeout_per_phase']),
            "debate_max_rounds": db_config.get('debate.max_rounds', self.DEFAULT_NODE_CONFIG['debate_max_rounds']),
            "trade_history_limit": db_config.get('debate.trade_history_limit', self.DEFAULT_NODE_CONFIG['trade_history_limit']),
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
        
        # 加载角色配置（从 system_configs）
        self.debate_roles = self._load_debate_roles(db_config)
        
        # 加载角色提示词（从文件，fallback 到默认值）
        self.debate_prompts = self._load_debate_prompts()
        
        logger.info(f"✅ DebateDecisionNode initialized with risk_limits from bot")
        logger.info(f"   max_total={self.node_config['max_total_allocation_pct']}%, max_single={self.node_config['max_single_allocation_pct']}%")
        logger.info(f"   辩论角色: {[r['id'] for r in self.debate_roles]}")
    
    def _load_debate_roles(self, db_config: Dict) -> List[Dict]:
        """
        从 system_configs 加载辩论角色配置
        
        Args:
            db_config: 从数据库读取的配置字典
            
        Returns:
            角色配置列表，每个元素包含 id, name, name_en, focus, style, priority
        """
        import json
        
        # 默认角色配置
        default_roles = [
            {"id": "analyst", "name": "市场分析师", "name_en": "Market Analyst", "priority": 1},
            {"id": "bull", "name": "多头交易员", "name_en": "Bull Trader", "priority": 2},
            {"id": "bear", "name": "空头交易员", "name_en": "Bear Trader", "priority": 2},
            {"id": "risk_manager", "name": "风险经理", "name_en": "Risk Manager", "priority": 3},
        ]
        
        # 尝试从配置加载
        roles_config = db_config.get('debate.roles')
        if roles_config:
            try:
                if isinstance(roles_config, str):
                    roles = json.loads(roles_config)
                else:
                    roles = roles_config
                logger.debug(f"📋 从配置加载 {len(roles)} 个辩论角色")
                return roles
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"⚠️ 解析 debate.roles 配置失败: {e}，使用默认角色")
        
        return default_roles
    
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
    
    def _build_trade_history_context(self, bot_id: int) -> str:
        """
        构建交易历史上下文
        
        包含最近 N 笔已平仓交易的详情，供 AI 学习：
        - 成功交易的共同特征
        - 失败交易的警示信号
        
        Args:
            bot_id: 机器人 ID
            
        Returns:
            格式化的交易历史上下文字符串
        """
        if not self.trade_history_repo:
            return ""
        
        limit = self.node_config.get('trade_history_limit', 10)
        
        try:
            trades = self.trade_history_repo.get_recent_trades(bot_id, limit)
        except Exception as e:
            logger.warning(f"⚠️ 获取交易历史失败: {e}")
            return ""
        
        if not trades:
            return ""
        
        # 分类统计
        wins = [t for t in trades if t.pnl_percent and float(t.pnl_percent) > 0]
        losses = [t for t in trades if t.pnl_percent and float(t.pnl_percent) <= 0]
        
        context = "## 📊 近期交易记录（供决策参考）\n\n"
        
        # 统计摘要
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_win = sum(float(t.pnl_percent) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(float(t.pnl_percent) for t in losses) / len(losses) if losses else 0
        
        context += f"**统计**: 最近 {len(trades)} 笔 | 胜率 {win_rate:.0f}% | "
        context += f"平均盈利 {avg_win:.1f}% | 平均亏损 {avg_loss:.1f}%\n\n"
        
        # 显示最近 5 笔交易详情
        context += "### 最近交易详情\n"
        for trade in trades[:5]:
            pnl = float(trade.pnl_percent or 0)
            result = "盈利" if pnl > 0 else "亏损"
            emoji = "✅" if pnl > 0 else "❌"
            
            entry = float(trade.entry_price) if trade.entry_price else 0
            exit_p = float(trade.exit_price) if trade.exit_price else 0
            
            context += f"- {emoji} **{trade.symbol}**: {trade.action}, "
            context += f"入场 ${entry:.4f}, 出场 ${exit_p:.4f}, "
            context += f"**{result} {pnl:+.2f}%**\n"
        
        # 如果有连续亏损，特别提醒
        consecutive_losses = 0
        for trade in trades:
            if trade.pnl_percent and float(trade.pnl_percent) <= 0:
                consecutive_losses += 1
            else:
                break
        
        if consecutive_losses >= 3:
            context += f"\n⚠️ **警告**: 连续 {consecutive_losses} 笔亏损，建议降低仓位或暂停交易！\n"
        
        return context + "\n"
    
    def _build_market_context(self, state: State) -> str:
        """
        构建市场数据上下文
        
        包含：
        - 绩效反馈（让 AI 根据历史表现调整策略）
        - 交易历史（让 AI 从具体案例中学习）
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
        
        # ========== 交易历史（供 AI 学习具体案例） ==========
        trade_history_context = self._build_trade_history_context(state.bot_id)
        if trade_history_context:
            context += trade_history_context
        
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
                
                # 计算 ROE（Return on Equity）= 价格变动 × 杠杆
                # 这与交易所显示的盈亏百分比一致
                if pos.side == 'buy':
                    # 多头：(现价 - 入场价) / 入场价
                    price_change_pct = ((current_price - pos.price) / pos.price * 100) if pos.price > 0 else 0
                else:
                    # 空头：(入场价 - 现价) / 入场价
                    price_change_pct = ((pos.price - current_price) / pos.price * 100) if pos.price > 0 else 0
                # ROE = 价格变动 × 杠杆
                pnl_pct = price_change_pct * pos.leverage
                
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
    
    async def _run_analyst(self, market_context: str, symbols: List[str]) -> List[AnalystOutput]:
        """
        Phase 1: 市场分析师分析
        
        使用 AnalystOutputList 包装类型一次性输出所有币种分析。
        使用 with_fallbacks 机制处理异常。
        
        Args:
            market_context: 市场数据上下文
            symbols: 候选币种列表（用于 fallback）
        """
        logger.info("📊 Phase 1: Analyst 分析市场...")
        
        # 使用 AnalystOutputList 包装类型，支持多币种输出
        llm = self._get_llm(role="analyst").with_structured_output(AnalystOutputList)
        timeout = self.node_config['timeout_per_phase']
        
        # 创建 fallback（为每个真实 symbol 返回中性分析）
        async def analyst_fallback(messages):
            logger.warning("⚠️ Analyst 使用 fallback - 返回中性分析")
            return AnalystOutputList(
                outputs=[
                    AnalystOutput(
                        symbol=sym,
                        trend="neutral",
                        key_levels=None,
                        summary="分析失败，默认中性判断"
                    ) for sym in symbols
                ]
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
            # 解包 AnalystOutputList -> List[AnalystOutput]
            outputs = result.outputs if isinstance(result, AnalystOutputList) else [result]
            logger.info(f"✅ Analyst 完成: {len(outputs)} 个币种分析")
            return outputs
        except asyncio.TimeoutError:
            logger.error(f"❌ Analyst 超时 ({timeout}s) - 使用默认中性分析")
            return [
                AnalystOutput(
                    symbol=sym,
                    trend="neutral",
                    key_levels=None,
                    summary="分析超时，默认中性"
                ) for sym in symbols
            ]
        except Exception as e:
            logger.error(f"❌ Analyst 失败: {e}")
            # 返回 fallback 结果而非空列表，避免后续处理失败
            return [
                AnalystOutput(
                    symbol=sym,
                    trend="neutral",
                    key_levels=None,
                    summary=f"分析出错: {str(e)[:50]}"
                ) for sym in symbols
            ]
    
    async def _run_single_debate_round(
        self,
        symbol: str,
        bull_human_msg: str,
        bear_human_msg: str,
        is_final_round: bool,
        timeout: int,
    ) -> Tuple[Any, Any]:
        """
        执行单轮辩论
        
        - 中间轮：输出自由文本观点（用于下轮反驳）
        - 最终轮：输出结构化 TraderSuggestion
        
        Args:
            symbol: 币种符号
            bull_human_msg: Bull 的输入消息
            bear_human_msg: Bear 的输入消息
            is_final_round: 是否为最终轮
            timeout: 超时时间（秒）
            
        Returns:
            (bull_result, bear_result) 元组
        """
        llm_bull = self._get_llm(role="bull")
        llm_bear = self._get_llm(role="bear")
        
        if is_final_round:
            # 最终轮：结构化输出 TraderSuggestion
            bull_chain = ChatPromptTemplate.from_messages([
                ("system", self.debate_prompts["bull"]),
                ("human", "{input}"),
            ]) | llm_bull.with_structured_output(TraderSuggestion)
            
            bear_chain = ChatPromptTemplate.from_messages([
                ("system", self.debate_prompts["bear"]),
                ("human", "{input}"),
            ]) | llm_bear.with_structured_output(TraderSuggestion)
            
            # Fallback for final round
            def create_fallback(role: str):
                async def fallback_fn(input_data):
                    logger.warning(f"⚠️ {role} fallback for {symbol}")
                    return TraderSuggestion(
                        symbol=symbol,
                        action="wait",
                        confidence=0,
                        allocation_pct=0,
                        stop_loss_pct=2.0,
                        take_profit_pct=6.0,
                        reasoning=f"{role} 分析失败，默认观望"
                    )
                return RunnableLambda(fallback_fn)
        else:
            # 中间轮：自由文本输出，简洁阐述观点
            bull_system = self.debate_prompts["bull"] + "\n\n请用 2-3 句话简洁阐述你对该币种的核心观点和理由。"
            bear_system = self.debate_prompts["bear"] + "\n\n请用 2-3 句话简洁阐述你对该币种的核心观点和理由。"
            
            bull_chain = ChatPromptTemplate.from_messages([
                ("system", bull_system),
                ("human", "{input}"),
            ]) | llm_bull
            
            bear_chain = ChatPromptTemplate.from_messages([
                ("system", bear_system),
                ("human", "{input}"),
            ]) | llm_bear
            
            # Fallback for intermediate round
            def create_fallback(role: str):
                async def fallback_fn(input_data):
                    logger.warning(f"⚠️ {role} 中间轮 fallback for {symbol}")
                    return f"{role} 无法分析，暂无观点。"
                return RunnableLambda(fallback_fn)
        
        # 添加 fallback
        bull_chain_safe = bull_chain.with_fallbacks(
            [create_fallback("Bull")],
            exceptions_to_handle=(Exception,)
        )
        bear_chain_safe = bear_chain.with_fallbacks(
            [create_fallback("Bear")],
            exceptions_to_handle=(Exception,)
        )
        
        # 并行执行 Bull 和 Bear（注意：需要分别传入不同的输入）
        try:
            bull_task = asyncio.create_task(
                asyncio.wait_for(
                    bull_chain_safe.ainvoke({"input": bull_human_msg}),
                    timeout=timeout
                )
            )
            bear_task = asyncio.create_task(
                asyncio.wait_for(
                    bear_chain_safe.ainvoke({"input": bear_human_msg}),
                    timeout=timeout
                )
            )
            
            bull_result, bear_result = await asyncio.gather(bull_task, bear_task, return_exceptions=True)
            
            # 处理异常结果
            if isinstance(bull_result, Exception):
                logger.error(f"❌ {symbol}: Bull 异常: {bull_result}")
                bull_result = None
            if isinstance(bear_result, Exception):
                logger.error(f"❌ {symbol}: Bear 异常: {bear_result}")
                bear_result = None
            
            return (bull_result, bear_result)
            
        except Exception as e:
            logger.error(f"❌ {symbol}: 辩论轮次失败: {e}")
            return (None, None)
    
    async def _run_multi_round_debate_for_symbol(
        self,
        symbol: str,
        market_context: str,
        analyst_summary: str,
    ) -> Tuple[Optional[TraderSuggestion], Optional[TraderSuggestion], List[DebateRound]]:
        """
        为单个币种执行多轮辩论
        
        LangChain 最佳实践：
        - 使用 ChatPromptTemplate 构建动态 prompt
        - 每轮将对方观点作为 HumanMessage 追加
        - 最终轮输出结构化建议
        
        Args:
            symbol: 币种符号
            market_context: 市场数据上下文
            analyst_summary: 分析师总结
            
        Returns:
            (bull_suggestion, bear_suggestion, debate_rounds) 元组
        """
        max_rounds = self.node_config.get("debate_max_rounds", 2)
        timeout = self.node_config.get("timeout_per_phase", 120)
        
        round_records: List[DebateRound] = []
        bull_opinion = ""
        bear_opinion = ""
        bull_result = None
        bear_result = None
        
        for round_num in range(1, max_rounds + 1):
            is_final_round = (round_num == max_rounds)
            
            # 构建本轮 prompt（包含对方上轮观点）
            if round_num == 1:
                # 第一轮：基础分析
                bull_human = f"目标币种: {symbol}\n\n分析师总结:\n{analyst_summary}\n\n市场数据:\n{market_context}\n\n请给出做多建议。"
                bear_human = f"目标币种: {symbol}\n\n分析师总结:\n{analyst_summary}\n\n市场数据:\n{market_context}\n\n请给出做空建议。"
            else:
                # 后续轮次：加入对方观点进行反驳
                bull_human = f"目标币种: {symbol}\n\n空头交易员的观点:\n{bear_opinion}\n\n请反驳以上观点，坚持你的做多立场，或修正你的判断。如果这是最终轮，请给出最终建议。"
                bear_human = f"目标币种: {symbol}\n\n多头交易员的观点:\n{bull_opinion}\n\n请反驳以上观点，坚持你的做空立场，或修正你的判断。如果这是最终轮，请给出最终建议。"
            
            # 执行单轮辩论
            round_bull, round_bear = await self._run_single_debate_round(
                symbol, bull_human, bear_human, is_final_round, timeout
            )
            
            # 提取观点文本（用于下轮反驳）
            if is_final_round:
                # 最终轮是结构化输出
                bull_result = round_bull
                bear_result = round_bear
                bull_opinion = round_bull.reasoning if round_bull else "无观点"
                bear_opinion = round_bear.reasoning if round_bear else "无观点"
                bull_action = round_bull.action if round_bull else None
                bear_action = round_bear.action if round_bear else None
            else:
                # 中间轮是文本输出
                if hasattr(round_bull, 'content'):
                    bull_opinion = round_bull.content
                else:
                    bull_opinion = str(round_bull) if round_bull else "无观点"
                
                if hasattr(round_bear, 'content'):
                    bear_opinion = round_bear.content
                else:
                    bear_opinion = str(round_bear) if round_bear else "无观点"
                
                bull_action = None
                bear_action = None
            
            # 记录本轮辩论
            round_records.append(DebateRound(
                round_number=round_num,
                symbol=symbol,
                bull_opinion=bull_opinion[:500],  # 截断存储
                bear_opinion=bear_opinion[:500],
                bull_action=bull_action,
                bear_action=bear_action,
            ))
            
            logger.info(f"   Round {round_num}/{max_rounds} for {symbol}: Bull={bull_action or 'opinion'}, Bear={bear_action or 'opinion'}")
        
        return (bull_result, bear_result, round_records)
    
    async def _run_phase2_parallel(
        self, 
        market_context: str, 
        analyst_summary: str,
        symbols: List[str],
    ) -> Tuple[List[TraderSuggestion], List[TraderSuggestion], List[DebateRound]]:
        """
        Phase 2: 多轮辩论
        
        为每个币种执行多轮辩论，Bull 和 Bear 互相质疑和反驳。
        
        Args:
            market_context: 市场数据上下文
            analyst_summary: 分析师总结
            symbols: 候选币种列表
            
        Returns:
            (bull_suggestions, bear_suggestions, all_debate_rounds) 元组
        """
        max_rounds = self.node_config.get("debate_max_rounds", 2)
        logger.info(f"📊 Phase 2: {max_rounds} 轮辩论，{len(symbols)} 个币种...")
        
        bull_suggestions: List[TraderSuggestion] = []
        bear_suggestions: List[TraderSuggestion] = []
        all_debate_rounds: List[DebateRound] = []
        
        # 为每个币种执行多轮辩论
        for symbol in symbols:
            bull_result, bear_result, rounds = await self._run_multi_round_debate_for_symbol(
                symbol, market_context, analyst_summary
            )
            if bull_result:
                bull_suggestions.append(bull_result)
            if bear_result:
                bear_suggestions.append(bear_result)
            all_debate_rounds.extend(rounds)
        
        logger.info(f"✅ Phase 2 完成: Bull={len(bull_suggestions)} 个, Bear={len(bear_suggestions)} 个, 辩论轮次={len(all_debate_rounds)}")
        return (bull_suggestions, bear_suggestions, all_debate_rounds)
    
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
    
    def _create_close_only_decisions(self, state: State) -> State:
        """
        只生成平仓决策（不开仓）
        
        用于震荡市/高波动市场景：
        - 不开新仓
        - 检查现有持仓是否需要平仓（止盈/止损/趋势反转）
        
        判断平仓条件：
        1. 止损：亏损 >= 3%
        2. 止盈：盈利 >= 10%，或盈利 >= 5% 且趋势减弱
        3. 趋势反转：技术面出现反转信号
        """
        decisions = []
        
        # ========== 1. 检查现有持仓 ==========
        for pos in state.positions:
            symbol = pos.symbol
            
            # 获取市场数据
            market_data = state.market_data.get(symbol, {})
            indicators = market_data.get('indicators', {})
            current_price = indicators.get('current_price', pos.price)
            
            # 计算 ROE（Return on Equity）= 价格变动 × 杠杆
            if pos.side == 'buy':
                price_change_pct = ((current_price - pos.price) / pos.price * 100) if pos.price > 0 else 0
            else:
                price_change_pct = ((pos.price - current_price) / pos.price * 100) if pos.price > 0 else 0
            pnl_pct = price_change_pct * pos.leverage
            
            # 获取技术指标
            rsi = indicators.get('rsi_4h') or indicators.get('rsi_3m', 50)
            # MACD 返回的是单个 float 值（MACD 主线），正值看涨，负值看跌
            macd_value = indicators.get('macd_4h', 0)
            macd_value = macd_value if isinstance(macd_value, (int, float)) else 0
            
            # ========== 判断是否需要平仓 ==========
            should_close = False
            close_reason = ""
            
            # 条件 1：止损（亏损 >= 3%）
            if pnl_pct <= -3:
                should_close = True
                close_reason = f"止损: 亏损 {pnl_pct:.2f}% >= 3%"
            
            # 条件 2：止盈（盈利 >= 10%）
            elif pnl_pct >= 10:
                should_close = True
                close_reason = f"止盈: 盈利 {pnl_pct:.2f}% >= 10%"
            
            # 条件 3：趋势减弱 + 有盈利（盈利 >= 5%）
            elif pnl_pct >= 5:
                # 多头：RSI 超买 + MACD 为负
                if pos.side == 'buy' and rsi > 70 and macd_value < 0:
                    should_close = True
                    close_reason = f"趋势减弱止盈: 盈利 {pnl_pct:.2f}%, RSI={rsi:.0f}>70, MACD<0"
                # 空头：RSI 超卖 + MACD 为正
                elif pos.side == 'sell' and rsi < 30 and macd_value > 0:
                    should_close = True
                    close_reason = f"趋势减弱止盈: 盈利 {pnl_pct:.2f}%, RSI={rsi:.0f}<30, MACD>0"
            
            # 条件 4：趋势反转信号（即使没有盈利也要考虑平仓）
            if not should_close:
                if pos.side == 'buy' and rsi > 75 and macd_value < 0:
                    should_close = True
                    close_reason = f"趋势反转: RSI={rsi:.0f}>75, MACD<0"
                elif pos.side == 'sell' and rsi < 25 and macd_value > 0:
                    should_close = True
                    close_reason = f"趋势反转: RSI={rsi:.0f}<25, MACD>0"
            
            # ========== 生成决策 ==========
            if should_close:
                close_action = "close_long" if pos.side == 'buy' else "close_short"
                decisions.append(PortfolioDecision(
                    symbol=symbol,
                    action=close_action,
                    allocation_pct=0,
                    confidence=90,
                    reasoning=close_reason,
                    priority=0,  # 最高优先级
                ))
                logger.info(f"🔴 {symbol}: 生成平仓决策 - {close_reason}")
            else:
                # 继续持有（wait）
                decisions.append(PortfolioDecision(
                    symbol=symbol,
                    action="wait",
                    allocation_pct=0,
                    confidence=50,
                    reasoning=f"震荡市继续持有: PnL={pnl_pct:+.2f}%, 未触发平仓条件",
                    priority=99,
                ))
                logger.info(f"⏸️ {symbol}: 继续持有 - PnL={pnl_pct:+.2f}%")
        
        # ========== 2. 候选币种全部设为 wait ==========
        position_symbols = {p.symbol for p in state.positions}
        for symbol in state.symbols:
            # 跳过已有持仓的币种（上面已处理）
            if symbol in position_symbols:
                continue
            
            decisions.append(PortfolioDecision(
                symbol=symbol,
                action="wait",
                allocation_pct=0,
                confidence=0,
                reasoning="震荡市，跳过开仓",
                priority=99,
            ))
        
        # ========== 3. 构建结果 ==========
        batch_result = BatchDecisionResult(
            decisions=decisions,
            total_allocation_pct=0,
            cash_reserve_pct=100,
            strategy_rationale=f"震荡市模式: 检查了 {len(state.positions)} 个持仓, 跳过 {len(state.symbols)} 个候选币种的开仓"
        )
        
        state.batch_decision = batch_result
        
        # 同时写入 debate_decision（与前端兼容）
        state.debate_decision = DebateDecisionResult(
            analyst_outputs=[],
            bull_suggestions=[],
            bear_suggestions=[],
            final_decision=batch_result,
            debate_summary="震荡市模式: 只检查平仓，不开仓",
            completed_at=datetime.now(),
        )
        
        logger.info(f"📊 震荡市决策完成: {len(decisions)} 个决策")
        return state
    
    def _get_forced_close_decisions(self, state: State) -> List[PortfolioDecision]:
        """
        检查需要强制平仓的持仓
        
        当持仓亏损超过 3% 时，生成强制平仓决策。
        这些决策将直接注入到最终结果中，不受 AI 决策影响。
        
        Returns:
            强制平仓决策列表
        """
        forced_decisions: List[PortfolioDecision] = []
        
        for pos in state.positions:
            # 获取当前价格
            market_data = state.market_data.get(pos.symbol, {})
            indicators = market_data.get('indicators', {})
            current_price = indicators.get('current_price', pos.price)
            
            # 计算 ROE（Return on Equity）= 价格变动 × 杠杆
            # 这与交易所显示的盈亏百分比一致
            if pos.side == 'buy':
                # 多头：(现价 - 入场价) / 入场价
                price_change_pct = ((current_price - pos.price) / pos.price * 100) if pos.price > 0 else 0
            else:
                # 空头：(入场价 - 现价) / 入场价
                price_change_pct = ((pos.price - current_price) / pos.price * 100) if pos.price > 0 else 0
            # ROE = 价格变动 × 杠杆
            pnl_pct = price_change_pct * pos.leverage
            
            # 亏损超过 3% 强制平仓（基于 ROE）
            if pnl_pct <= -3:
                close_action = "close_long" if pos.side == 'buy' else "close_short"
                forced_decisions.append(PortfolioDecision(
                    symbol=pos.symbol,
                    action=close_action,
                    allocation_pct=0,
                    confidence=100,
                    reasoning=f"强制止损: 未实现亏损 {pnl_pct:.2f}% 超过 3% 阈值",
                    priority=0,  # 最高优先级
                ))
                logger.warning(f"🛑 强制平仓: {pos.symbol} 亏损 {pnl_pct:.2f}%")
        
        return forced_decisions
    
    def _normalize_allocations(self, result: BatchDecisionResult, valid_symbols: List[str]) -> BatchDecisionResult:
        """
        规范化仓位分配
        
        包括：
        1. Symbol 存在性校验（移除不在候选列表中的决策）
        2. 单币种仓位限制
        3. 总仓位限制
        
        Args:
            result: 待规范化的决策结果
            valid_symbols: 有效的候选币种列表
        """
        max_total = self.node_config['max_total_allocation_pct']
        max_single = self.node_config['max_single_allocation_pct']
        
        # ========== Step 1: Symbol 存在性校验 ==========
        valid_decisions = []
        for d in result.decisions:
            if d.symbol in valid_symbols:
                valid_decisions.append(d)
            else:
                logger.error(f"❌ 无效 Symbol 已移除: {d.symbol} (不在候选列表 {valid_symbols} 中)")
        result.decisions = valid_decisions
        
        # ========== Step 2: 单币种仓位限制 ==========
        for d in result.decisions:
            if d.allocation_pct > max_single:
                logger.warning(f"⚠️ {d.symbol}: {d.allocation_pct}% > max {max_single}%")
                d.allocation_pct = max_single
        
        # ========== Step 3: 总仓位限制 ==========
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
        logger.info(f"   候选币种: {state.symbols}")
        logger.info("=" * 60)
        
        # 检查是否启用辩论机制
        if not self.node_config.get("debate_enabled", True):
            logger.info("⏭️ 辩论机制已禁用 (debate.enabled=false)，跳过")
            # 返回空的批量决策
            state.batch_decision = self._create_default_decisions(state)
            return state
        
        # ========== 市场状态检查 ==========
        regime = getattr(state, 'market_regime', None)
        if regime:
            logger.info(f"📊 市场状态: {regime} (置信度: {getattr(state, 'regime_confidence', 0):.1%})")
            
            if regime == "ranging":
                # 震荡市：跳过新开仓，只检查持仓是否需要平仓
                logger.warning("⏸️ 震荡市检测 (market_regime=ranging)")
                logger.warning("   跳过新开仓，只检查持仓是否需要平仓")
                return self._create_close_only_decisions(state)
            
            if regime == "volatile":
                # 高波动市：降低仓位限制
                logger.warning("⚠️ 高波动市检测 (market_regime=volatile)")
                logger.warning("   降低仓位限制，更严格的风控")
                original_max = self.node_config.get('max_single_allocation_pct', 30)
                self.node_config['max_single_allocation_pct'] = min(original_max, 15)
        
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
        
        # Phase 1: Analyst（传入 symbols 用于 fallback）
        analyst_outputs = await self._run_analyst(market_context, state.symbols)
        analyst_summary = "\n".join([
            f"{a.symbol}: {a.trend}, {a.summary}" 
            for a in analyst_outputs
        ]) if analyst_outputs else "分析师未提供分析"
        
        # Phase 2: 多轮辩论（Bull + Bear 互相质疑）
        bull_suggestions, bear_suggestions, debate_rounds = await self._run_phase2_parallel(
            market_context, analyst_summary, state.symbols
        )
        
        # Phase 3: RiskManager
        batch_result = await self._run_risk_manager(
            state, market_context, bull_suggestions, bear_suggestions
        )
        
        # ========== 注入强制平仓决策 ==========
        # 检查持仓亏损超过 3% 的，强制生成平仓决策
        forced_decisions = self._get_forced_close_decisions(state)
        if forced_decisions:
            logger.info(f"🛑 注入 {len(forced_decisions)} 个强制平仓决策")
            # 移除与强制平仓冲突的 AI 决策
            forced_symbols = {d.symbol for d in forced_decisions}
            batch_result.decisions = [
                d for d in batch_result.decisions 
                if d.symbol not in forced_symbols
            ]
            # 将强制平仓决策插入到最前面（最高优先级）
            batch_result.decisions = forced_decisions + batch_result.decisions
        
        # 规范化仓位（包含 symbol 校验）
        # 构建有效 symbol 列表：候选币种 + 持仓币种
        # 修复 BUG：持仓币种可能被量化过滤掉，但平仓决策仍需保留
        valid_symbols = list(state.symbols)
        if state.positions:
            for pos in state.positions:
                if pos.symbol not in valid_symbols:
                    valid_symbols.append(pos.symbol)
                    logger.info(f"📌 添加持仓币种到有效列表: {pos.symbol}")
        
        batch_result = self._normalize_allocations(batch_result, valid_symbols)
        
        # -------------------------
        # 保存辩论过程到 state.debate_decision
        # -------------------------
        max_rounds = self.node_config.get("debate_max_rounds", 2)
        debate_summary = (
            f"Analyst: {len(analyst_outputs)} reports, "
            f"Debate: {max_rounds} rounds, "
            f"Bull: {len(bull_suggestions)} suggestions, "
            f"Bear: {len(bear_suggestions)} suggestions"
        )
        
        state.debate_decision = DebateDecisionResult(
            analyst_outputs=analyst_outputs,
            bull_suggestions=bull_suggestions,
            bear_suggestions=bear_suggestions,
            debate_rounds=debate_rounds,  # 新增：保存多轮辩论记录
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

