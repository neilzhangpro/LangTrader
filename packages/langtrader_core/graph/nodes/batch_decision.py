# packages/langtrader_core/graph/nodes/batch_decision.py
"""
批量决策节点 (Batch Decision Node)

设计参考 NoFx prompt_builder.go：
- 一次 LLM 调用处理所有候选币种
- 输出包含仓位分配的投资组合决策
- 确保总仓位不超过限制

替代原有的 decision.py（每币种独立调用 LLM）
"""
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import (
    State, 
    BatchDecisionResult, 
    PortfolioDecision,
    PerformanceMetrics,
    DebateDecisionResult,
)
from langtrader_core.utils import get_logger
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from pathlib import Path
from datetime import datetime
import json
import asyncio

logger = get_logger("batch_decision")


class BatchDecision(NodePlugin):
    """
    批量决策节点
    
    核心特性：
    1. 一次 LLM 调用处理所有候选币种（而非每个币种单独调用）
    2. 输出带有仓位分配比例的批量决策
    3. 自动验证和规范化仓位分配（确保 <= 80%）
    
    配置来源（统一从 bots.risk_limits 读取）：
    - 风控约束：max_total_allocation_pct, max_single_allocation_pct 等
    - 节点配置：timeout_seconds 从 system_configs 读取
    """
    
    metadata = NodeMetadata(
        name="batch_decision",
        display_name="Batch Decision",
        version="2.1.0",
        author="LangTrader official",
        description="批量决策节点：一次 LLM 调用处理所有币种，输出仓位协调的投资组合决策",
        category="decision",
        tags=["decision", "batch", "portfolio", "official"],
        inputs=["symbols", "market_data"],
        outputs=["batch_decision"],
        requires=["quant_signal_filter"],
        requires_llm=True,
        insert_after="quant_signal_filter",
        suggested_order=4,
        auto_register=False  # 模式2禁用：使用 debate_decision 替代
    )
    
    # 节点运行时默认配置（非风控配置）
    DEFAULT_NODE_CONFIG = {
        "timeout_seconds": 90,
    }
    
    # 风控默认配置（仅作为 fallback，优先从 bot.risk_limits 读取）
    # 注意：百分比使用整数格式（80 = 80%），资金费率使用小数格式（0.05 = 0.05%）
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
    
    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        
        # -------------------------
        # 依赖注入：从 context 获取共享资源
        # -------------------------
        if not context:
            logger.error("🚨 Context not found")
            raise ValueError("Context not found")
        
        self.llm_factory = context.llm_factory if hasattr(context, 'llm_factory') else None
        self.performance_service = context.performance_service if hasattr(context, 'performance_service') else None
        self.trader = context.trader if hasattr(context, 'trader') else None
        self.database = context.database if hasattr(context, 'database') else None
        self.bot = context.bot if hasattr(context, 'bot') else None  # 保存 bot 引用用于获取 llm_id
        
        if not self.llm_factory:
            logger.error("🚨 LLM factory not found in context")
            raise ValueError("LLM factory not found in context")
        
        # ========== 统一配置加载 ==========
        # 1. 从 bot.risk_limits 读取风控约束（唯一配置源）
        self.risk_limits = {}
        if self.bot:
            self.risk_limits = self.bot.risk_limits or {}
            logger.debug(f"Loaded risk_limits from bot: {list(self.risk_limits.keys())}")
        
        # 2. 从 system_configs 读取节点配置
        db_config = self.load_config_from_database('batch_decision')
        
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
            
            # 计算最小现金储备（基于总仓位上限）
            "min_cash_reserve_pct": 100 - self.risk_limits.get('max_total_allocation_pct', self.DEFAULT_RISK_LIMITS['max_total_allocation_pct']),
            
            # 节点配置（从 system_configs 读取）
            "timeout_seconds": db_config.get('batch_decision.timeout_seconds', self.DEFAULT_NODE_CONFIG['timeout_seconds']),
        }
        
        # 覆盖传入的 config
        if config:
            self.node_config.update(config)
        
        # LLM 实例（延迟初始化）
        self._llm = None
        self._llm_with_structure = None
        
        logger.info(f"✅ BatchDecision initialized with risk_limits from bot")
        logger.info(f"   max_total={self.node_config['max_total_allocation_pct']}%, max_single={self.node_config['max_single_allocation_pct']}%")
    
    def _get_llm(self):
        """
        获取或创建 LLM 实例
        
        优先级：bot.llm_id > default LLM
        """
        if self._llm is None:
            # 优先使用 bot 配置的 LLM
            if self.bot and hasattr(self.bot, 'llm_id') and self.bot.llm_id:
                logger.info(f"Using bot-specific LLM: llm_id={self.bot.llm_id}")
                self._llm = self.llm_factory.create_from_id(self.bot.llm_id)
            else:
                # 否则使用默认 LLM
                logger.info("Using default LLM")
                self._llm = self.llm_factory.create_default()
            logger.info(f"✅ LLM created: {self._llm.model_name}")
        return self._llm
    
    def _get_llm_with_structure(self):
        """获取带有结构化输出的 LLM"""
        if self._llm_with_structure is None:
            llm = self._get_llm()
            self._llm_with_structure = llm.with_structured_output(BatchDecisionResult)
            logger.debug("✅ LLM with structured output created")
        return self._llm_with_structure
    
    def _load_system_prompt(self, filename: str = "batch_decision.txt") -> str:
        """
        加载系统提示词
        
        Args:
            filename: 提示词文件名
            
        Returns:
            系统提示词内容
        """
        current_dir = Path(__file__).parent
        prompts_dir = current_dir.parent.parent / "prompts"
        file_path = prompts_dir / filename
        
        if not file_path.exists():
            logger.warning(f"⚠️ Prompt file not found: {file_path}, using default")
            return self._get_default_system_prompt()
        
        content = file_path.read_text(encoding='utf-8')
        if not content:
            logger.warning(f"⚠️ Empty prompt file: {filename}, using default")
            return self._get_default_system_prompt()
        
        logger.debug(f"📄 Loaded system prompt from {filename}")
        return content
    
    def _get_default_system_prompt(self) -> str:
        """默认系统提示词（如果文件不存在）"""
        return """你是专业的量化交易AI，负责分析市场数据并做出交易决策。

## 核心原则

1. **风险优先**：保护资本比追求收益更重要
2. **仓位协调**：所有决策的仓位总和不超过 80%
3. **质量优先**：少量高信念交易胜过大量低信念交易

## 输出格式

输出 JSON 格式的批量决策，包含所有候选币种的决策。"""
    
    def _build_user_prompt(self, state: State, performance: PerformanceMetrics = None) -> str:
        """
        构建用户提示词（包含所有币种的市场数据）
        
        设计参考 NoFx BuildUserPrompt：
        - 账户状态
        - 当前持仓
        - 所有候选币种的分析
        - 约束条件
        """
        prompt = ""
        
        # -------------------------
        # 1. 绩效反馈（如果有）
        # -------------------------
        if performance and performance.total_trades > 0:
            prompt += performance.to_prompt_text()
            prompt += "\n"
        
        # -------------------------
        # 2. 账户状态
        # -------------------------
        prompt += "# 账户状态\n"
        prompt += "-------------------\n"
        
        total_balance = 0.0
        free_balance = 0.0
        
        # 计算已用保证金（考虑杠杆）
        used_margin = 0.0
        if state.positions:
            used_margin = sum(pos.margin_used for pos in state.positions)
        
        if state.account:
            # 支持 USDT 和 USDC
            total_balance = state.account.total.get('USDT', 0) or state.account.total.get('USDC', 0)
            free_balance = state.account.free.get('USDT', 0) or state.account.free.get('USDC', 0)
            
            prompt += f"- 总资产: ${total_balance:.2f}（包含持仓锁定）\n"
            prompt += f"- **可用余额: ${free_balance:.2f}** ⚠️ 分配仓位时必须基于此值计算\n"
            prompt += f"- 已用保证金: ${used_margin:.2f}\n"
            prompt += f"- 初始余额: ${state.initial_balance or 0:.2f}\n"
            
            # 计算可开仓额度（总额度 - 已用保证金）
            max_total_margin = free_balance * (self.node_config['max_total_allocation_pct'] / 100)
            available_margin = max(0, max_total_margin - used_margin)
            margin_usage_pct = (used_margin / max_total_margin * 100) if max_total_margin > 0 else 0
            prompt += f"- 可开仓额度: ${available_margin:.2f}（已用 {margin_usage_pct:.1f}%）\n"
            
            # 计算示例，帮助 AI 正确理解
            min_alloc_for_10usd = (10.0 / free_balance * 100) if free_balance > 0 else 100
            prompt += f"\n💡 **allocation_pct 计算基准**: 可用余额 ${free_balance:.2f}\n"
            prompt += f"   例如：开 $10 仓位 → allocation_pct = {min_alloc_for_10usd:.1f}%\n"
        else:
            prompt += "- 账户信息不可用\n"
        
        prompt += "-------------------\n\n"
        
        # -------------------------
        # 3. 当前持仓（优先评估是否需要平仓！）
        # -------------------------
        prompt += "# 🔔 当前持仓（优先评估是否需要平仓！）\n"
        prompt += "-------------------\n"
        prompt += "**重要**：请先检查以下持仓是否需要平仓（止盈/止损/趋势反转），再考虑新开仓！\n\n"
        
        if state.positions:
            for pos in state.positions:
                # 获取该币种的当前价格
                market_data = state.market_data.get(pos.symbol, {})
                indicators = market_data.get('indicators', {})
                current_price = indicators.get('current_price', pos.price)
                
                # 计算未实现盈亏
                if pos.side == 'buy':
                    pnl_pct = ((current_price - pos.price) / pos.price * 100) if pos.price > 0 else 0
                else:
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
                
                side_cn = "多头" if pos.side == 'buy' else "空头"
                prompt += f"- {pos.symbol} ({side_cn}): 入场${pos.price:.4f} → 现价${current_price:.4f}, "
                prompt += f"**盈亏: {pnl_pct:+.2f}%** {pnl_emoji}\n"
                prompt += f"  数量={pos.amount:.6f}, 杠杆={pos.leverage}x, 保证金=${pos.margin_used:.2f}\n"
                prompt += f"  💡 建议: {action_hint}\n"
                
                # 只有亏损超过3%时才强烈建议平仓
                if pnl_pct <= -3:
                    close_action = "close_long" if pos.side == 'buy' else "close_short"
                    prompt += f"  ⚡ **强制操作: `{close_action}` 止损离场**\n"
        else:
            prompt += "无持仓，可考虑新开仓。\n"
        
        prompt += "-------------------\n\n"
        
        # -------------------------
        # 4. 所有候选币种（核心：一次性列出）
        # -------------------------
        prompt += "# 候选币种分析\n"
        prompt += "（以下是所有候选币种，请综合分析后给出批量决策）\n\n"
        
        for symbol in state.symbols:
            prompt += f"## {symbol}\n"
            prompt += "-------------------\n"
            
            # 量化信号和指标（来自 market_state + quant_signal_filter）
            market_data = state.market_data.get(symbol, {})
            indicators = market_data.get('indicators', {})
            quant_signal = indicators.get('quant_signal', {})
            
            # 当前价格（关键：LLM 需要此信息计算止盈止损价格）
            current_price = indicators.get('current_price', 0)
            if current_price:
                prompt += f"当前价格: ${current_price:.4f}\n"
            
            if quant_signal:
                prompt += f"量化得分: {quant_signal.get('total_score', 'N/A')}/100\n"
                breakdown = quant_signal.get('breakdown', {})
                prompt += f"  - 趋势: {breakdown.get('trend', 'N/A')}\n"
                prompt += f"  - 动量: {breakdown.get('momentum', 'N/A')}\n"
                prompt += f"  - 量能: {breakdown.get('volume', 'N/A')}\n"
                prompt += f"  - 情绪: {breakdown.get('sentiment', 'N/A')}\n"
            
            # 资金费率
            funding_rate = indicators.get('funding_rate', 0)
            if funding_rate is not None:
                prompt += f"资金费率: {funding_rate*100:.4f}%\n"
            
            prompt += "-------------------\n\n"
        
        # -------------------------
        # 5. 约束条件（风控硬约束）
        # -------------------------
        prompt += "# ⚠️ 风控约束（必须遵守）\n"
        prompt += "-------------------\n"
        prompt += f"- 总仓位上限: {self.node_config['max_total_allocation_pct']:.0f}%\n"
        prompt += f"- 单币种上限: {self.node_config['max_single_allocation_pct']:.0f}%\n"
        prompt += f"- 最小开仓金额: ${self.node_config['min_position_size_usd']:.0f}\n"
        prompt += f"- 最大开仓金额: ${self.node_config['max_position_size_usd']:.0f}\n"
        prompt += f"- 最小风险回报比: {self.node_config['min_risk_reward_ratio']:.1f}:1\n"
        prompt += f"- 最大杠杆: {self.node_config['max_leverage']}x\n"
        prompt += f"- 推荐杠杆: {self.node_config['default_leverage']}x\n"
        prompt += f"- 资金费率上限: {self.node_config['max_funding_rate_pct']:.2f}%\n"
        prompt += f"- 可用资金: ${free_balance:.2f}\n"
        prompt += "-------------------\n\n"
        
        # -------------------------
        # 6. 输出格式说明
        # -------------------------
        prompt += "# 输出要求\n"
        prompt += self._get_output_format_guide()
        
        return prompt
    
    def _get_output_format_guide(self) -> str:
        """输出格式指南"""
        schema = BatchDecisionResult.model_json_schema()
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False)
        
        return f"""
请输出 JSON 格式的批量决策：

## 输出 Schema
{schema_str}

## 关键规则

1. **仓位分配**:
   - 为每个币种分配 allocation_pct（占总余额的百分比）
   - 所有 allocation_pct 之和 <= 80%
   - 如果某币种决定 wait，allocation_pct = 0

2. **优先级 priority**:
   - 如果有多个 open 决策，按信心度排序
   - priority=1 最先执行

3. **reasoning 必填**:
   - 详细说明决策理由
   - 便于后续回溯分析

4. **止损止盈（必须是具体价格，不是百分比！）**:
   - **Long（做多）**: stop_loss < current_price < take_profit
     示例：当前价格 $100 → 止损 $95, 止盈 $110
   - **Short（做空）**: take_profit < current_price < stop_loss
     示例：当前价格 $100 → 止盈 $90, 止损 $105
   - 风险回报比 >= 2:1
   - ⚠️ 做空的止损止盈方向与做多相反！
"""
    
    def _normalize_allocations(self, result: BatchDecisionResult) -> BatchDecisionResult:
        """
        规范化仓位分配，确保不超过限制
        
        如果总分配超过 max_total_allocation_pct，按比例缩减
        """
        max_total = self.node_config['max_total_allocation_pct']
        max_single = self.node_config['max_single_allocation_pct']
        
        # 计算实际总分配
        total = sum(d.allocation_pct for d in result.decisions if d.action not in ("wait", "hold"))
        
        if total <= 0:
            logger.debug("📊 No allocation needed (all wait/hold)")
            result.total_allocation_pct = 0
            result.cash_reserve_pct = 100
            return result
        
        # 检查单币种限制
        for d in result.decisions:
            if d.allocation_pct > max_single:
                logger.warning(f"⚠️ {d.symbol}: allocation {d.allocation_pct}% > max {max_single}%, capping")
                d.allocation_pct = max_single
        
        # 重新计算总分配
        total = sum(d.allocation_pct for d in result.decisions if d.action not in ("wait", "hold"))
        
        # 如果总分配超限，按比例缩减
        if total > max_total:
            scale_factor = max_total / total
            logger.warning(f"⚠️ Total allocation {total:.1f}% > max {max_total}%, scaling by {scale_factor:.2f}")
            
            for d in result.decisions:
                if d.action not in ("wait", "hold"):
                    d.allocation_pct *= scale_factor
        
        # 更新汇总
        result.total_allocation_pct = sum(d.allocation_pct for d in result.decisions if d.action not in ("wait", "hold"))
        result.cash_reserve_pct = 100 - result.total_allocation_pct
        
        logger.info(f"📊 Final allocation: {result.total_allocation_pct:.1f}%, cash reserve: {result.cash_reserve_pct:.1f}%")
        
        return result
    
    
    async def run(self, state: State) -> State:
        """
        执行批量决策
        
        流程：
        1. 加载绩效数据
        2. 构建批量提示词
        3. 一次 LLM 调用
        4. 规范化仓位分配
        5. 同步到 runs
        """
        logger.info("=" * 60)
        logger.info("🎯 BatchDecision 开始执行")
        logger.info(f"   候选币种数: {len(state.symbols)}")
        logger.info("=" * 60)
        
        # -------------------------
        # 1. 加载绩效指标
        # -------------------------
        performance = None
        if self.performance_service:
            try:
                performance = self.performance_service.calculate_metrics(state.bot_id)
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
                logger.info(f"📊 绩效加载: sharpe={performance.sharpe_ratio:.2f}, trades={performance.total_trades}")
            except Exception as e:
                logger.warning(f"⚠️ 绩效加载失败: {e}")
        
        # -------------------------
        # 2. 构建提示词
        # -------------------------
        system_prompt = self._load_system_prompt()
        user_prompt = self._build_user_prompt(state, performance=state.performance)
        
        logger.debug(f"📝 System prompt length: {len(system_prompt)} chars")
        logger.debug(f"📝 User prompt length: {len(user_prompt)} chars")
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        
        # -------------------------
        # 3. LLM 调用（一次处理所有币种）- 使用 with_fallbacks
        # -------------------------
        llm = self._get_llm_with_structure()
        timeout = self.node_config['timeout_seconds']
        
        # 创建 fallback（返回默认 wait 决策）
        # 注意：使用闭包捕获 state
        default_decisions = self._create_default_wait_decisions(state)
        
        async def decision_fallback(msgs):
            logger.warning("⚠️ LLM 决策使用 fallback - 返回默认 wait 决策")
            return default_decisions
        
        # 带 fallback 的 chain
        safe_llm = llm.with_fallbacks(
            [RunnableLambda(decision_fallback)],
            exceptions_to_handle=(Exception,)
        )
        
        logger.info(f"🤖 调用 LLM（超时: {timeout}s）...")
        
        try:
            batch_result = await asyncio.wait_for(
                safe_llm.ainvoke(messages),
                timeout=timeout
            )
            
            logger.info(f"✅ LLM 返回 {len(batch_result.decisions)} 个决策")
            
            # 打印决策摘要
            for d in batch_result.decisions:
                logger.info(f"   {d.symbol}: {d.action}, alloc={d.allocation_pct:.1f}%, conf={d.confidence}")
            
        except asyncio.TimeoutError:
            logger.error(f"❌ LLM 调用超时 ({timeout}s) - 使用默认决策")
            batch_result = default_decisions
        except Exception as e:
            logger.error(f"❌ LLM 调用失败: {e} - 使用默认决策")
            batch_result = default_decisions
        
        # -------------------------
        # 4. 规范化仓位分配
        # -------------------------
        batch_result = self._normalize_allocations(batch_result)
        
        # -------------------------
        # 5. 保存到 state
        # -------------------------
        state.batch_decision = batch_result
        
        # 同时写入 debate_decision 供前端展示（无辩论过程，仅有最终决策）
        state.debate_decision = DebateDecisionResult(
            analyst_outputs=[],
            bull_suggestions=[],
            bear_suggestions=[],
            final_decision=batch_result,
            debate_summary=f"Batch decision: {len(batch_result.decisions)} decisions",
            completed_at=datetime.now(),
        )
        
        logger.info("=" * 60)
        logger.info(f"🎯 BatchDecision 完成")
        logger.info(f"   总仓位: {batch_result.total_allocation_pct:.1f}%")
        logger.info(f"   现金储备: {batch_result.cash_reserve_pct:.1f}%")
        logger.info("=" * 60)
        
        return state
    
    def _create_default_wait_decisions(self, state: State) -> BatchDecisionResult:
        """创建默认的 wait 决策（LLM 失败时使用）"""
        decisions = []
        for symbol in state.symbols:
            decisions.append(PortfolioDecision(
                symbol=symbol,
                action="wait",
                allocation_pct=0,
                confidence=0,
                reasoning="LLM 调用失败，默认观望"
            ))
        
        return BatchDecisionResult(
            decisions=decisions,
            total_allocation_pct=0,
            cash_reserve_pct=100,
            strategy_rationale="LLM 调用失败，全部观望"
        )

