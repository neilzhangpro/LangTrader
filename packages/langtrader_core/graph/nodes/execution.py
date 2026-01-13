import math
from langtrader_core.graph.state import (
    State, AIDecision, ExecutionResult, OpenPositionResult,
    BatchDecisionResult, PortfolioDecision,
)
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.services.trailing_stop import TrailingStopManager
from langtrader_core.utils import get_logger
from typing import Dict, Any, Optional, Tuple, List

logger = get_logger("execution")


# ==================== 风控硬约束检查结果 ====================
class RiskCheckResult:
    """风控检查结果"""
    def __init__(self, passed: bool, reason: str = "", warning: str = ""):
        self.passed = passed
        self.reason = reason  # 如果失败，说明原因
        self.warning = warning  # 警告信息（通过但需注意）
    
    def __bool__(self):
        return self.passed


class Execution(NodePlugin):
    """
    执行决策节点
    
    从 state.batch_decision 读取决策并执行：
    - 按 priority 排序执行
    - 检查可用余额
    - 执行风控硬约束检查
    
    配置来源（统一从 bots.risk_limits 读取）：
    风控约束与 debate_decision / batch_decision 共享同一配置源
    """
    
    metadata = NodeMetadata(
        name="execution",
        display_name="Execution",
        version="2.1.0",
        author="LangTrader official",
        description="执行决策节点：执行风控硬约束检查并下单",
        category="Basic",
        tags=["execution", "official"],
        insert_after="debate_decision",  # 模式2：跟在辩论决策后
        suggested_order=5,
        auto_register=True
    )
    
    # 风控默认配置（仅作为 fallback，优先从 bot.risk_limits 读取）
    # 注意：百分比使用整数格式（80 = 80%），资金费率使用小数格式（0.05 = 0.05%）
    DEFAULT_RISK_LIMITS = {
        "max_total_allocation_pct": 80.0,      # 总仓位上限 80%
        "max_single_allocation_pct": 30.0,     # 单币种上限 30%
        "max_leverage": 5,
        "max_consecutive_losses": 5,
        "max_daily_loss_pct": 5.0,             # 单日最大亏损 5%
        "max_drawdown_pct": 15.0,              # 最大回撤 15%
        "max_funding_rate_pct": 0.05,          # 资金费率上限 0.05%（正常市场范围）
        "funding_rate_check_enabled": True,
        "min_position_size_usd": 10.0,
        "max_position_size_usd": 5000.0,
        "min_risk_reward_ratio": 2.0,
        "hard_stop_enabled": True,
        "pause_on_consecutive_loss": True,
        "pause_on_max_drawdown": True,
    }

    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        self.trader = context.trader if context else None
        self.stream_manager = context.stream_manager if context else None
        self.trade_history_repo = context.trade_history_repo if context else None
        self.bot_id = None  # 在 run 中从 state 获取
        
        # ========== 统一配置加载 ==========
        # 从 bot.risk_limits 读取风控约束（唯一配置源）
        self.risk_limits = {}
        if context and hasattr(context, 'bot') and context.bot:
            self.risk_limits = context.bot.risk_limits or {}
            logger.debug(f"Loaded risk_limits from bot: {list(self.risk_limits.keys())}")
        
        # 允许 config 覆盖（用于测试或特殊场景）
        if config and 'risk_limits' in config:
            self.risk_limits.update(config['risk_limits'])
        
        # ========== 追踪止损管理器 ==========
        # 从 risk_limits 中读取追踪止损配置
        self.trailing_stop_manager = TrailingStopManager(self.risk_limits)
        
        logger.info(f"✅ Execution initialized with risk_limits from bot")
    
    # ==================== 风控硬约束检查 ====================
    # 所有风控参数从 bot.risk_limits 数据库配置加载
    
    def _load_risk_limits(self, state: State) -> Dict[str, Any]:
        """
        加载风控配置
        
        优先级：
        1. bot.risk_limits (self.risk_limits)
        2. 默认值 (DEFAULT_RISK_LIMITS)
        
        注意：所有百分比使用 % 格式（如 80 表示 80%），需要在使用时转换
        """
        # 合并默认值和 bot 配置
        limits = {**self.DEFAULT_RISK_LIMITS, **self.risk_limits}
        
        # 转换为小数格式用于计算（如 80% -> 0.8）
        return {
            # 百分比转小数
            "max_total_exposure_pct": limits.get('max_total_allocation_pct', 80) / 100,
            "max_single_symbol_pct": limits.get('max_single_allocation_pct', 30) / 100,
            "max_daily_loss_pct": limits.get('max_daily_loss_pct', 5) / 100,
            "max_drawdown_pct": limits.get('max_drawdown_pct', 15) / 100,
            "max_funding_rate_pct": limits.get('max_funding_rate_pct', 0.1) / 100,
            
            # 非百分比字段直接使用
            "max_leverage": limits.get('max_leverage', 10),
            "max_consecutive_losses": limits.get('max_consecutive_losses', 5),
            "funding_rate_check_enabled": limits.get('funding_rate_check_enabled', True),
            "min_position_size_usd": limits.get('min_position_size_usd', 10),
            "max_position_size_usd": limits.get('max_position_size_usd', 10000),
            "min_risk_reward_ratio": limits.get('min_risk_reward_ratio', 2.0),
            "hard_stop_enabled": limits.get('hard_stop_enabled', True),
            "pause_on_consecutive_loss": limits.get('pause_on_consecutive_loss', True),
            "pause_on_max_drawdown": limits.get('pause_on_max_drawdown', True),
        }
    
    def _check_risk_constraints(
        self,
        decision: AIDecision,
        state: State,
        position_size_usd: float,
    ) -> RiskCheckResult:
        """
        风控硬约束检查（在下单前执行）
        
        检查项目：
        1. 总敞口限制
        2. 单币种敞口限制
        3. 杠杆限制
        4. 仓位大小限制
        5. 连续亏损检查
        6. 资金费率检查
        7. 最大回撤检查
        
        Returns:
            RiskCheckResult: 检查结果
        """
        limits = self._load_risk_limits(state)
        symbol = decision.symbol
        
        logger.debug(f"🔒 Risk check for {symbol}: size=${position_size_usd:.2f}")
        
        # ========== 1. 仓位大小限制 ==========
        min_size = limits.get('min_position_size_usd', 10.0)
        max_size = limits.get('max_position_size_usd', 10000.0)
        
        if position_size_usd < min_size:
            return RiskCheckResult(
                passed=False,
                reason=f"Position size ${position_size_usd:.2f} < min ${min_size:.2f}"
            )
        
        if position_size_usd > max_size:
            return RiskCheckResult(
                passed=False,
                reason=f"Position size ${position_size_usd:.2f} > max ${max_size:.2f}"
            )
        
        # ========== 2. 杠杆限制 ==========
        max_leverage = limits.get('max_leverage', 10)
        if decision.leverage and decision.leverage > max_leverage:
            return RiskCheckResult(
                passed=False,
                reason=f"Leverage {decision.leverage}x > max {max_leverage}x"
            )
        
        # ========== 3. 总保证金使用率限制 ==========
        # 统一使用「保证金」概念：已用保证金 / 可用余额
        max_margin_usage = limits.get('max_total_exposure_pct', 0.8)
        free_balance = 0.0
        if state.account:
            free_balance = state.account.free.get('USDT', 0) or state.account.free.get('USDC', 0)
        
        if free_balance > 0:
            # 计算当前持仓已用保证金
            # 保证金 = 名义价值 / 杠杆 = (amount * price) / leverage
            current_margin = 0.0
            if state.positions:
                for pos in state.positions:
                    # 使用 Position 的 margin_used 属性（已处理杠杆）
                    current_margin += pos.margin_used
                    logger.debug(f"   {pos.symbol}: notional=${pos.notional_value:.2f}, "
                               f"leverage={pos.leverage}x, margin=${pos.margin_used:.2f}")
            
            # 新开仓的保证金 = position_size_usd（AI 分配的就是保证金）
            new_margin = position_size_usd
            total_margin = current_margin + new_margin
            margin_usage_pct = total_margin / free_balance
            
            logger.debug(f"🔒 Margin check: current=${current_margin:.2f}, "
                        f"new=${new_margin:.2f}, total=${total_margin:.2f}, "
                        f"usage={margin_usage_pct*100:.1f}%")
            
            if margin_usage_pct > max_margin_usage:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Total margin usage {margin_usage_pct*100:.1f}% > max {max_margin_usage*100:.1f}%"
                )
        
        # ========== 4. 单币种保证金限制 ==========
        max_single_pct = limits.get('max_single_symbol_pct', 0.3)
        if free_balance > 0:
            single_pct = position_size_usd / free_balance
            if single_pct > max_single_pct:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Single symbol margin {single_pct*100:.1f}% > max {max_single_pct*100:.1f}%"
                )
        
        # ========== 5. 连续亏损检查 ==========
        if limits.get('pause_on_consecutive_loss', True):
            max_consecutive = limits.get('max_consecutive_losses', 5)
            consecutive_losses = self._get_consecutive_losses(state)
            
            if consecutive_losses >= max_consecutive:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Consecutive losses {consecutive_losses} >= max {max_consecutive}, trading paused"
                )
        
        # ========== 6. 资金费率检查 ==========
        if limits.get('funding_rate_check_enabled', True):
            max_funding = limits.get('max_funding_rate_pct', 0.001)
            funding_rate = self._get_funding_rate(state, symbol)
            
            if funding_rate is not None and abs(funding_rate) > max_funding:
                # 如果做多且资金费率为正（多头付费），或做空且资金费率为负（空头付费）
                if (decision.action == "open_long" and funding_rate > max_funding) or \
                   (decision.action == "open_short" and funding_rate < -max_funding):
                    return RiskCheckResult(
                        passed=False,
                        reason=f"Funding rate {funding_rate*100:.4f}% exceeds limit {max_funding*100:.4f}%"
                    )
        
        # ========== 7. 最大回撤检查 ==========
        if limits.get('pause_on_max_drawdown', True):
            max_drawdown = limits.get('max_drawdown_pct', 0.15)
            current_drawdown = self._get_current_drawdown(state)
            
            if current_drawdown is not None and current_drawdown > max_drawdown:
                return RiskCheckResult(
                    passed=False,
                    reason=f"Current drawdown {current_drawdown*100:.1f}% > max {max_drawdown*100:.1f}%, trading paused"
                )
        
        # ========== 所有检查通过 ==========
        logger.info(f"✅ {symbol}: Risk check passed")
        return RiskCheckResult(passed=True)
    
    def _get_consecutive_losses(self, state: State) -> int:
        """获取连续亏损次数"""
        if not self.trade_history_repo or not self.bot_id:
            return 0
        
        try:
            # 从交易历史获取最近的交易
            recent_trades = self.trade_history_repo.get_recent_trades(
                self.bot_id, limit=10
            )
            
            consecutive = 0
            for trade in recent_trades:
                if hasattr(trade, 'pnl_usd') and trade.pnl_usd is not None:
                    if trade.pnl_usd < 0:
                        consecutive += 1
                    else:
                        break  # 遇到盈利交易，停止计数
            
            return consecutive
        except Exception as e:
            logger.warning(f"⚠️ Failed to get consecutive losses: {e}")
            return 0
    
    def _get_funding_rate(self, state: State, symbol: str) -> Optional[float]:
        """获取资金费率"""
        market_data = state.market_data.get(symbol, {})
        indicators = market_data.get('indicators', {})
        return indicators.get('funding_rate')
    
    def _get_current_drawdown(self, state: State) -> Optional[float]:
        """获取当前回撤"""
        if not state.performance:
            return None
        
        if hasattr(state.performance, 'max_drawdown'):
            return state.performance.max_drawdown
        
        return None

    async def run(self, state: State):
        """
        执行决策节点
        
        执行顺序：
        1. 追踪止损检查（优先级最高）
        2. 批量决策执行
        """
        self.bot_id = state.bot_id
        
        logger.info("=" * 60)
        logger.info("🚀 Execution 开始执行")
        logger.info("=" * 60)
        
        # ========== 1. 追踪止损检查（优先于 AI 决策） ==========
        if self.trailing_stop_manager.enabled and state.positions:
            await self._check_and_execute_trailing_stops(state)
        
        # -------------------------
        # 2. 执行批量决策模式
        # -------------------------
        if state.batch_decision and state.batch_decision.decisions:
            logger.info("📋 使用批量决策模式 (batch_decision)")
            return await self._execute_batch(state)
        
        # -------------------------
        # 没有决策，直接返回
        # -------------------------
        logger.warning("⚠️ 没有 batch_decision，跳过执行")
        return state
    
    async def _check_and_execute_trailing_stops(self, state: State) -> List[ExecutionResult]:
        """
        检查并执行追踪止损
        
        遍历所有持仓，检查是否触发追踪止损条件，如果触发则执行平仓。
        
        Returns:
            执行结果列表
        """
        logger.info("📊 Checking trailing stops...")
        results = []
        
        # 获取需要平仓的持仓列表
        to_close = self.trailing_stop_manager.check_positions(
            positions=state.positions,
            market_data=state.market_data
        )
        
        if not to_close:
            logger.info("   No trailing stop triggered")
            return results
        
        logger.info(f"🛑 {len(to_close)} trailing stop(s) triggered!")
        
        for position, close_action in to_close:
            symbol = position.symbol
            
            # 构建平仓决策
            close_decision = AIDecision(
                symbol=symbol,
                action=close_action,
                leverage=position.leverage,
                position_size_usd=0,
                reasons=["Trailing stop triggered"]
            )
            
            # 执行平仓
            result = await self._execute_close(close_decision)
            results.append(result)
            
            if result.status == "success":
                # 清除追踪状态
                self.trailing_stop_manager.clear_position(symbol)
                logger.info(f"✅ {symbol}: Trailing stop close executed")
                
                # 从 state.positions 中移除
                state.positions = [p for p in state.positions if p.symbol != symbol]
            else:
                logger.error(f"❌ {symbol}: Trailing stop close failed - {result.message}")
        
        return results
    
    async def _execute_batch(self, state: State) -> State:
        """
        执行批量决策
        
        特点：
        1. 按优先级排序执行
        2. 动态检查可用余额
        3. 支持部分执行（余额不足时跳过低优先级决策）
        """
        batch = state.batch_decision
        
        # 过滤出需要执行的决策（非 wait/hold）
        actionable = [d for d in batch.decisions if d.action not in ("wait", "hold")]
        
        if not actionable:
            logger.info("⏸️ 无需执行的决策（全部 wait/hold）")
            return state
        
        # 按优先级排序（priority 小的先执行）
        sorted_decisions = sorted(actionable, key=lambda d: d.priority)
        
        logger.info(f"📊 待执行决策: {len(sorted_decisions)} 个")
        for d in sorted_decisions:
            logger.info(f"   P{d.priority}: {d.symbol} {d.action} alloc={d.allocation_pct:.1f}%")
        
        # ========== 获取初始可用余额 ==========
        free_balance = 0.0
        if state.account:
            free_balance = state.account.free.get('USDT', 0) or state.account.free.get('USDC', 0)
        
        # ========== 预检查：计算总保证金需求并按比例调整 ==========
        # 筛选开仓决策
        open_decisions = [d for d in sorted_decisions if d.action in ("open_long", "open_short")]
        
        if open_decisions and free_balance > 0:
            # 计算总保证金需求
            # 保证金 = 名义价值 / 杠杆 = (allocation_pct / 100) * free_balance / leverage
            total_margin_needed = 0.0
            for d in open_decisions:
                leverage = d.leverage if d.leverage > 0 else 1
                nominal_value = (d.allocation_pct / 100) * free_balance
                margin_needed = nominal_value / leverage
                total_margin_needed += margin_needed
                logger.debug(f"   {d.symbol}: 名义 ${nominal_value:.2f}, 杠杆 {leverage}x, 保证金 ${margin_needed:.2f}")
            
            # 最大可用保证金（预留 20% 安全边际，防止资金费率/滑点等）
            max_available_margin = free_balance * 0.8
            
            logger.info(f"📊 保证金预检查: 需求 ${total_margin_needed:.2f}, 可用 ${max_available_margin:.2f}")
            
            # 如果总保证金需求超过可用余额，按比例缩减
            if total_margin_needed > max_available_margin:
                scale_factor = max_available_margin / total_margin_needed
                logger.warning(f"⚠️ 保证金需求超限，按 {scale_factor:.2f} 比例缩减仓位")
                
                for d in open_decisions:
                    original_alloc = d.allocation_pct
                    d.allocation_pct = original_alloc * scale_factor
                    logger.info(f"   {d.symbol}: {original_alloc:.1f}% → {d.allocation_pct:.1f}%")
        
        # 跟踪已使用的保证金
        used_margin = 0.0
        success_count = 0
        
        # ========== 依次执行决策 ==========
        for portfolio_decision in sorted_decisions:
            symbol = portfolio_decision.symbol
            action = portfolio_decision.action
            leverage = portfolio_decision.leverage if portfolio_decision.leverage > 0 else 1
            
            # ========== 平仓操作：不需要检查余额，直接执行 ==========
            if action in ("close_long", "close_short"):
                logger.info(f"🔴 {symbol}: 执行平仓 ({action})")
                ai_decision = self._portfolio_to_ai_decision(portfolio_decision, 0)
                result = await self._execute_close_with_validation(ai_decision, state, symbol)
                if result.status == "success":
                    logger.info(f"✅ {symbol}: 平仓成功")
                    # 平仓后刷新余额
                    if self.trader:
                        try:
                            account_info = await self.trader.get_account_info()
                            free_balance = account_info.free.get('USDT', 0) or account_info.free.get('USDC', 0)
                            logger.info(f"   💰 刷新余额: ${free_balance:.2f}")
                        except Exception as e:
                            logger.warning(f"   ⚠️ 刷新余额失败: {e}")
                else:
                    logger.warning(f"❌ {symbol}: 平仓失败 - {result.message}")
                continue
            
            # ========== 开仓操作：需要检查余额 ==========
            # 计算名义价值和保证金
            nominal_value = (portfolio_decision.allocation_pct / 100) * free_balance
            margin_needed = nominal_value / leverage
            
            # 检查剩余可用保证金
            remaining_margin = free_balance - used_margin
            
            if margin_needed > remaining_margin:
                logger.warning(
                    f"⚠️ {symbol}: 保证金不足 (需要 ${margin_needed:.2f}, 剩余 ${remaining_margin:.2f})"
                )
                # 如果剩余保证金太少，跳过
                if remaining_margin < margin_needed * 0.5 or remaining_margin < 10:
                    logger.warning(f"⏭️ {symbol}: 跳过（剩余保证金不足）")
                    self._record_skip(state, symbol, portfolio_decision, "Insufficient margin")
                    continue
                else:
                    # 使用剩余保证金（留 10% 安全边际）
                    margin_needed = remaining_margin * 0.9
                    nominal_value = margin_needed * leverage
                    logger.info(f"   调整: 保证金 ${margin_needed:.2f}, 名义价值 ${nominal_value:.2f}")
            
            # 转换为 AIDecision 并执行（使用名义价值）
            ai_decision = self._portfolio_to_ai_decision(portfolio_decision, nominal_value)
            
            # 执行开仓
            if action in ("open_long", "open_short"):
                result = await self._execute_open_with_validation(ai_decision, state, symbol)
                
                if result.status == "success":
                    success_count += 1
                    used_margin += margin_needed
                    
                    # 🔧 关键修复：每笔订单成功后从交易所刷新真实余额
                    if self.trader:
                        try:
                            account_info = await self.trader.get_account_info()
                            new_free_balance = account_info.free.get('USDT', 0) or account_info.free.get('USDC', 0)
                            
                            # 更新 used_margin 为实际消耗
                            actual_used = free_balance - new_free_balance
                            if actual_used > 0:
                                used_margin = actual_used
                            
                            free_balance = new_free_balance
                            logger.info(f"   💰 刷新余额: ${free_balance:.2f} (实际已用 ${used_margin:.2f})")
                        except Exception as e:
                            logger.warning(f"   ⚠️ 刷新余额失败: {e}")
                else:
                    logger.warning(f"❌ {symbol}: 开仓失败 - {result.message}")
            else:
                result = ExecutionResult(
                    symbol=symbol,
                    action=action,
                    status="skipped",
                    message="Unknown action"
                )
        
        logger.info(f"💰 执行完成: {success_count}/{len(open_decisions)} 个开仓, 已用保证金 ${used_margin:.2f}")
        
        return state
    
    def _portfolio_to_ai_decision(self, pd: PortfolioDecision, position_size_usd: float) -> AIDecision:
        """将 PortfolioDecision 转换为 AIDecision"""
        return AIDecision(
            symbol=pd.symbol,
            action=pd.action,
            leverage=pd.leverage,
            position_size_usd=position_size_usd,
            stop_loss_price=pd.stop_loss,
            take_profit_price=pd.take_profit,
            confidence=pd.confidence,  # PortfolioDecision.confidence 已是 int
            risk_approved=pd.risk_approved,
            reasons=[pd.reasoning] if pd.reasoning else []
        )
    
    def _record_skip(self, state: State, symbol: str, pd: PortfolioDecision, reason: str):
        """记录跳过的决策（日志记录）"""
        logger.debug(f"⏭️ {symbol}: Skipped - {reason}")
    
    async def _execute_open_with_validation(self, decision: AIDecision, state: State, symbol: str) -> ExecutionResult:
        """执行开仓（带验证和风控检查）"""
        # ========== 1. 验证参数 ==========
        if not self._validate_open_params(decision):
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message="Invalid parameters"
            )
        
        if not self._validate_open_position(decision):
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message="Invalid position logic"
            )
        
        # ========== 2. 风控硬约束检查 ==========
        risk_check = self._check_risk_constraints(
            decision=decision,
            state=state,
            position_size_usd=decision.position_size_usd,
        )
        
        if not risk_check.passed:
            logger.warning(f"🛑 {symbol}: Risk check FAILED - {risk_check.reason}")
            
            # 记录到 alerts，供下一轮 AI 读取并调整策略
            state.alerts.append(f"[{symbol}] 风控拒绝: {risk_check.reason}")
            
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",  # ExecutionResult 只支持 skipped/pending/success/failed
                message=f"Risk limit: {risk_check.reason}"
            )
        
        if risk_check.warning:
            logger.warning(f"⚠️ {symbol}: Risk warning - {risk_check.warning}")
        
        # ========== 3. 获取 cycle_id ==========
        cycle_id = str(state.bot_id) if state.bot_id else None
        
        # ========== 4. 执行开仓 ==========
        return await self._execute_open(decision, state, cycle_id)
    
    async def _execute_close_with_validation(self, decision: AIDecision, state: State, symbol: str) -> ExecutionResult:
        """执行平仓（带验证）"""
        if not await self._validate_close_position(decision, state):
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message="No position to close"
            )
        
        return await self._execute_close(decision)

    def _validate_open_params(self, decision: AIDecision) -> bool:
        """验证开仓参数是否完整"""
        symbol = decision.symbol

        if decision.leverage is None or decision.leverage <= 0:
            logger.error(f"🚨 {symbol}: Invalid leverage={decision.leverage}")
            return False

        if decision.position_size_usd is None or decision.position_size_usd <= 0:
            logger.error(f"🚨 {symbol}: Invalid position_size_usd={decision.position_size_usd}")
            return False

        if decision.stop_loss_price is None or decision.stop_loss_price <= 0:
            logger.error(f"🚨 {symbol}: Invalid stop_loss_price={decision.stop_loss_price}")
            return False

        if decision.take_profit_price is None or decision.take_profit_price <= 0:
            logger.error(f"🚨 {symbol}: Invalid take_profit_price={decision.take_profit_price}")
            return False

        return True

    def _validate_open_position(self, decision: AIDecision) -> bool:
        """验证开仓决策的合理性"""
        symbol = decision.symbol

        # 验证止盈止损方向
        if decision.action == "open_long":
            if decision.stop_loss_price >= decision.take_profit_price:
                logger.error(f"🚨 {symbol}: Long invalid: SL({decision.stop_loss_price}) >= TP({decision.take_profit_price})")
                return False
        elif decision.action == "open_short":
            if decision.stop_loss_price <= decision.take_profit_price:
                logger.error(f"🚨 {symbol}: Short invalid: SL({decision.stop_loss_price}) <= TP({decision.take_profit_price})")
                return False

        # 验证风险回报比 (reward/risk >= 3)
        if decision.risk_usd is not None and decision.risk_usd > 0:
            reward = decision.position_size_usd - decision.risk_usd
            if reward <= 0:
                logger.error(f"🚨 {symbol}: Invalid reward={reward}")
                return False
            rr_ratio = reward / decision.risk_usd
            if rr_ratio < 3.0:
                logger.error(f"🚨 {symbol}: R:R ratio {rr_ratio:.2f} < 3.0")
                return False
            logger.info(f"✅ {symbol}: R:R ratio = {rr_ratio:.2f}")

        return True

    async def _validate_close_position(self, decision: AIDecision, state: State = None) -> bool:
        """
        验证平仓决策
        
        优化：优先使用 state.positions（每轮开始已刷新），避免重复 API 请求
        """
        symbol = decision.symbol
        logger.info(f"🔍 Validating close position: {symbol}")

        if self.trader is None:
            logger.error(f"🚨 {symbol}: Trader not available")
            return False

        # 1. 优先从 state.positions 获取（每轮开始已刷新）
        position = None
        if state and state.positions:
            logger.debug(f"📦 {symbol}: Checking state.positions ({len(state.positions)} positions)")
            position = next((p for p in state.positions if p.symbol == symbol), None)
            if position:
                logger.info(f"📦 {symbol}: Found in cache - side={position.side}, amount={position.amount}")
            else:
                logger.info(f"📦 {symbol}: Not found in state.positions cache")
        
        # 2. 回退到 API 查询
        if position is None:
            logger.info(f"📡 {symbol}: Fetching position from exchange...")
            position = await self.trader.get_position(symbol)
        
        if position is None:
            logger.error(f"🚨 {symbol}: No position found to close")
            return False

        # 验证平仓方向匹配
        if decision.action == "close_long" and position.side != "buy":
            logger.error(f"🚨 {symbol}: Cannot close_long, current side={position.side}")
            return False
        elif decision.action == "close_short" and position.side != "sell":
            logger.error(f"🚨 {symbol}: Cannot close_short, current side={position.side}")
            return False

        return True

    async def _execute_open(self, decision: AIDecision, state: State = None, cycle_id: str = None) -> ExecutionResult:
        """
        执行开仓
        
        优化：优先使用 state.market_data 中的价格，避免重复请求交易所 API
        """
        symbol = decision.symbol
        
        logger.info(f"🚀 Opening position: {symbol} {decision.action}")
        logger.info(f"   Leverage: {decision.leverage}x")
        logger.info(f"   Size: ${decision.position_size_usd}")
        logger.info(f"   SL: {decision.stop_loss_price}, TP: {decision.take_profit_price}")
        
        if self.trader is None:
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message="Trader not available"
            )
        
        # 确定下单方向
        side = "buy" if decision.action == "open_long" else "sell"
        position_side = "long" if decision.action == "open_long" else "short"
        
        # 🔧 获取当前市场价格（优先使用 state 中已有的价格）
        current_price = None
        
        # 1. 优先从 state.market_data 获取（避免重复请求）
        if state and symbol in state.market_data:
            indicators = state.market_data[symbol].get('indicators', {})
            current_price = indicators.get('current_price')
            if current_price and current_price > 0:
                logger.debug(f"📦 {symbol}: Using cached price ${current_price:.4f}")
        
        # 2. 回退到 API 请求（仅在缓存无效时）
        if not current_price or current_price <= 0:
            try:
                ticker = await self.trader.exchange.fetch_ticker(symbol)
                current_price = ticker['last'] if ticker else None
            except Exception as e:
                logger.error(f"❌ {symbol}: Failed to fetch price: {e}")
                return ExecutionResult(
                    symbol=symbol,
                    action=decision.action,
                    status="failed",
                    message=f"Failed to fetch price: {e}"
                )
        
        if not current_price or current_price <= 0:
            logger.error(f"❌ {symbol}: Unable to get current price")
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message="Unable to get current price"
            )
        
        # 计算币的数量 = USD金额 / 价格
        raw_amount = decision.position_size_usd / current_price
        
        # 🔧 修复：向上取整到交易所精度，避免精度截断后金额低于最低限制
        # Hyperliquid 等交易所会对 amount 进行精度截断（向下取整），
        # 导致 $10.03 -> 0.003228 ETH -> 截断为 0.0032 ETH -> $9.94 < $10 最低限制
        amount_in_coins = raw_amount
        if self.trader and self.trader.exchange:
            market = self.trader.exchange.markets.get(symbol, {})
            precision_info = market.get('precision', {})
            
            # 获取数量精度（小数位数）
            amount_precision = precision_info.get('amount')
            if amount_precision is not None:
                # 向上取整到该精度，确保截断后金额仍然 >= 目标金额
                multiplier = 10 ** int(amount_precision)
                amount_in_coins = math.ceil(raw_amount * multiplier) / multiplier
                
                adjusted_usd = amount_in_coins * current_price
                logger.debug(f"   🔧 Precision fix: {raw_amount:.8f} -> {amount_in_coins:.8f} "
                           f"(precision={amount_precision}, adjusted=${adjusted_usd:.2f})")
        
        logger.info(f"   💱 Converting: ${decision.position_size_usd} @ ${current_price:.4f} = {amount_in_coins:.6f} {symbol.split('/')[0]}")
        
        # 调用一键开仓（使用币的数量）
        # 注意：对于 Hyperliquid 等交易所，市价单需要传递 price 来计算滑点
        result = await self.trader.open_position(
            symbol=symbol,
            side=side,
            amount=amount_in_coins,
            leverage=decision.leverage,
            stop_loss=decision.stop_loss_price,
            take_profit=decision.take_profit_price,
            order_type="market",
            price=current_price,  # 传递当前价格用于滑点计算
        )
        
        # 构建执行结果
        if result.main and result.main.success:
            # 详细日志：订单执行情况
            order_status = result.main.status or 'unknown'
            filled = result.main.filled or 0
            remaining = result.main.remaining or 0
            average_price = result.main.average
            order_id = result.main.order_id
            
            logger.info(
                f"📊 {symbol}: Order execution details | "
                f"Status: {order_status} | "
                f"Filled: {filled} | Remaining: {remaining} | "
                f"Avg Price: {average_price}"
            )
            
            # ========== 使用交易所成交确认（方案C） ==========
            # 如果订单创建成功但 filled==0，轮询等待成交确认
            if filled == 0 and order_id:
                logger.info(f"⏳ {symbol}: Waiting for order fill confirmation...")
                confirmed_result = await self.trader.wait_for_order_fill(
                    order_id=order_id,
                    symbol=symbol,
                    max_wait_seconds=5.0,
                    poll_interval=0.5
                )
                
                if confirmed_result:
                    # 更新成交信息
                    order_status = confirmed_result.status or order_status
                    filled = confirmed_result.filled or 0
                    remaining = confirmed_result.remaining or 0
                    average_price = confirmed_result.average or average_price
                    
                    logger.info(
                        f"📊 {symbol}: Confirmed order status | "
                        f"Status: {order_status} | Filled: {filled} | "
                        f"Avg Price: {average_price}"
                    )
                    
                    # 更新 result.main 的值
                    result.main.status = order_status
                    result.main.filled = filled
                    result.main.remaining = remaining
                    result.main.average = average_price
            
            # 检查订单是否真正成交（对于市价单，应该是 closed 或 filled）
            if order_status not in ['closed', 'filled'] and filled == 0:
                logger.warning(
                    f"⚠️ {symbol}: Order status is '{order_status}' with no fills. "
                    f"Order might still be pending execution."
                )
            
            exec_result = ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="success" if filled > 0 else "pending",
                message=f"Position opened (Status: {order_status}, Filled: {filled})",
                order_id=order_id,
                executed_price=average_price,
                executed_amount=filled,
                fee_paid=result.main.fee,
                orders=result,
            )
            
            # 记录交易到数据库（使用实际成交的币数量）
            # 只有在有实际成交时才记录
            if filled > 0 and self.trade_history_repo and self.bot_id:
                try:
                    self.trade_history_repo.create(
                        bot_id=self.bot_id,
                        symbol=symbol,
                        side=position_side,
                        action=decision.action,
                        amount=filled,
                        entry_price=average_price,
                        leverage=decision.leverage,
                        cycle_id=cycle_id,
                        order_id=order_id,
                    )
                    logger.info(f"📝 Trade recorded: {symbol} {position_side} amount={filled:.6f} @ {average_price}")
                except Exception as e:
                    logger.error(f"❌ Failed to record trade: {e}")
            elif filled == 0:
                logger.warning(
                    f"⚠️ {symbol}: Not recording trade to database - order has no fills. "
                    f"Status: {order_status}"
                )
            
            return exec_result
        else:
            error_msg = result.main.error if result.main else "Unknown error"
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message=error_msg,
                orders=result,
            )

    async def _execute_close(self, decision: AIDecision) -> ExecutionResult:
        """执行平仓"""
        symbol = decision.symbol
        
        logger.info(f"🚀 Closing position: {symbol} {decision.action}")
        
        if self.trader is None:
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message="Trader not available"
            )
        
        # 获取开仓交易记录（用于计算 PnL）
        open_trade = None
        if self.trade_history_repo and self.bot_id:
            open_trade = self.trade_history_repo.get_open_trade_by_symbol(
                self.bot_id, symbol
            )
        
        # 调用平仓
        result = await self.trader.close_position(symbol)
        
        if result.success:
            # ========== 使用交易所成交确认（方案C） ==========
            order_id = result.order_id
            filled = result.filled or 0
            average_price = result.average
            order_status = result.status or 'unknown'
            fee = result.fee
            
            # 如果 filled==0，轮询等待成交确认
            if filled == 0 and order_id:
                logger.info(f"⏳ {symbol}: Waiting for close order fill confirmation...")
                confirmed_result = await self.trader.wait_for_order_fill(
                    order_id=order_id,
                    symbol=symbol,
                    max_wait_seconds=5.0,
                    poll_interval=0.5
                )
                
                if confirmed_result:
                    order_status = confirmed_result.status or order_status
                    filled = confirmed_result.filled or 0
                    average_price = confirmed_result.average or average_price
                    # 手续费可能在确认后更新
                    if confirmed_result.raw and confirmed_result.raw.get('fee'):
                        fee = confirmed_result.raw['fee'].get('cost', fee)
                    
                    logger.info(
                        f"📊 {symbol}: Confirmed close order | "
                        f"Status: {order_status} | Filled: {filled} | "
                        f"Avg Price: {average_price}"
                    )
            
            exec_result = ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="success" if filled > 0 else "pending",
                message=f"Position closed (Status: {order_status}, Filled: {filled})",
                order_id=order_id,
                executed_price=average_price,
                executed_amount=filled,
                fee_paid=fee,
            )
            
            # 清除追踪止损状态（如果有）
            self.trailing_stop_manager.clear_position(symbol)
            
            # 更新交易记录并计算 PnL
            # 只有确认成交后才更新
            if open_trade and average_price and filled > 0:
                try:
                    entry_price = float(open_trade.entry_price) if open_trade.entry_price else 0
                    exit_price = average_price
                    amount = float(open_trade.amount) if open_trade.amount else 0
                    
                    # 🔧 修复：正确计算盈亏
                    # amount 是币的数量，需要计算 USD 价值差
                    if open_trade.side == "long":
                        # 多头：买入时花费 entry_price * amount，卖出时获得 exit_price * amount
                        cost_basis = entry_price * amount
                        value_now = exit_price * amount
                        pnl_usd = value_now - cost_basis
                    else:  # short
                        # 空头：卖出时获得 entry_price * amount，买回时花费 exit_price * amount
                        value_entry = entry_price * amount
                        cost_exit = exit_price * amount
                        pnl_usd = value_entry - cost_exit
                    
                    # 扣除手续费
                    if fee:
                        pnl_usd -= fee
                    
                    # 计算百分比（相对于成本）
                    cost_basis = entry_price * amount if entry_price and amount else 0
                    pnl_percent = (pnl_usd / cost_basis * 100) if cost_basis > 0 else 0
                    
                    # 更新交易记录
                    self.trade_history_repo.close_trade(
                        trade_id=open_trade.id,
                        exit_price=exit_price,
                        pnl_usd=pnl_usd,
                        pnl_percent=pnl_percent,
                        fee_paid=fee,
                    )
                    logger.info(f"📝 Trade closed: {symbol} PnL: ${pnl_usd:.2f} ({pnl_percent:+.2f}%)")
                except Exception as e:
                    logger.error(f"❌ Failed to update trade: {e}")
            elif not open_trade:
                logger.warning(f"⚠️ {symbol}: No open trade record found, cannot calculate PnL")
            elif filled == 0:
                logger.warning(f"⚠️ {symbol}: Close order has no fills, not updating trade record")
            
            return exec_result
        else:
            error_msg = result.error or "Unknown error"
            logger.error(f"❌ {symbol}: Close position failed - {error_msg}")
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message=error_msg,
            )
