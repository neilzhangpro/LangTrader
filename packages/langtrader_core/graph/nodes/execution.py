from langtrader_core.graph.state import (
    State, AIDecision, ExecutionResult, OpenPositionResult
)
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.utils import get_logger

logger = get_logger("execution")


class Execution(NodePlugin):
    """执行决策节点"""
    
    metadata = NodeMetadata(
        name="execution",
        display_name="Execution",
        version="1.0.0",
        author="LangTrader official",
        description="The node that executes the decision.",
        category="Basic",
        tags=["execution", "official"],
        insert_after="risk_monitor",
        suggested_order=7,
        auto_register=True
    )

    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        self.trader = context.trader if context else None
        self.stream_manager = context.stream_manager if context else None
        self.trade_history_repo = context.trade_history_repo if context else None
        self.bot_id = None  # 在 run 中从 state 获取

    async def run(self, state: State):
        """执行决策节点"""
        self.bot_id = state.bot_id
        
        for symbol, run_record in state.runs.items():
            if run_record.decision is None:
                logger.warning(f"⚠️ {symbol}: No decision found, skipping")
                continue

            decision = run_record.decision

            # 根据 action 类型分流处理
            if decision.action in ("wait", "hold"):
                logger.info(f"⏸️ {symbol}: action={decision.action}, no trade")
                run_record.execution = ExecutionResult(
                    symbol=symbol,
                    action=decision.action,
                    status="skipped",
                    message="No action required"
                )
                continue

            if decision.action in ("open_long", "open_short"):
                # 开仓：需要验证参数和风险
                if not self._validate_open_params(decision):
                    run_record.execution = ExecutionResult(
                        symbol=symbol,
                        action=decision.action,
                        status="failed",
                        message="Invalid parameters"
                    )
                    continue
                    
                if not self._validate_open_position(decision):
                    run_record.execution = ExecutionResult(
                        symbol=symbol,
                        action=decision.action,
                        status="failed",
                        message="Invalid position logic"
                    )
                    continue
                    
                # 通过验证，执行开仓
                run_record.decision.risk_approved = True
                result = await self._execute_open(decision, run_record.cycle_id)
                run_record.execution = result

            elif decision.action in ("close_long", "close_short"):
                # 平仓：需要验证持仓存在
                if not await self._validate_close_position(decision):
                    run_record.execution = ExecutionResult(
                        symbol=symbol,
                        action=decision.action,
                        status="failed",
                        message="No position to close"
                    )
                    continue
                    
                # 通过验证，执行平仓
                run_record.decision.risk_approved = True
                result = await self._execute_close(decision)
                run_record.execution = result

            else:
                logger.warning(f"⚠️ {symbol}: Unknown action={decision.action}")

        return state

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

    async def _validate_close_position(self, decision: AIDecision) -> bool:
        """验证平仓决策"""
        symbol = decision.symbol

        if self.trader is None:
            logger.error(f"🚨 {symbol}: Trader not available")
            return False

        # 检查是否有持仓
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

    async def _execute_open(self, decision: AIDecision, cycle_id: str = None) -> ExecutionResult:
        """执行开仓"""
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
        
        # 调用一键开仓
        result = await self.trader.open_position(
            symbol=symbol,
            side=side,
            amount=decision.position_size_usd,
            leverage=decision.leverage,
            stop_loss=decision.stop_loss_price,
            take_profit=decision.take_profit_price,
            order_type="market",
        )
        
        # 构建执行结果
        if result.main and result.main.success:
            exec_result = ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="success",
                message="Position opened",
                order_id=result.main.order_id,
                executed_price=result.main.average,
                executed_amount=result.main.filled,
                fee_paid=result.main.fee,
                orders=result,
            )
            
            # 记录交易到数据库
            if self.trade_history_repo and self.bot_id:
                try:
                    self.trade_history_repo.create(
                        bot_id=self.bot_id,
                        symbol=symbol,
                        side=position_side,
                        action=decision.action,
                        amount=result.main.filled or decision.position_size_usd,
                        entry_price=result.main.average,
                        leverage=decision.leverage,
                        cycle_id=cycle_id,
                        order_id=result.main.order_id,
                    )
                    logger.info(f"📝 Trade recorded: {symbol} {position_side}")
                except Exception as e:
                    logger.error(f"❌ Failed to record trade: {e}")
            
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
            exec_result = ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="success",
                message="Position closed",
                order_id=result.order_id,
                executed_price=result.average,
                executed_amount=result.filled,
                fee_paid=result.fee,
            )
            
            # 更新交易记录并计算 PnL
            if open_trade and result.average:
                try:
                    entry_price = float(open_trade.entry_price) if open_trade.entry_price else 0
                    exit_price = result.average
                    amount = float(open_trade.amount) if open_trade.amount else 0
                    
                    # 计算盈亏
                    if open_trade.side == "long":
                        pnl_usd = (exit_price - entry_price) * amount
                    else:  # short
                        pnl_usd = (entry_price - exit_price) * amount
                    
                    # 扣除手续费
                    if result.fee:
                        pnl_usd -= result.fee
                    
                    # 计算百分比
                    pnl_percent = (pnl_usd / (entry_price * amount) * 100) if entry_price and amount else 0
                    
                    # 更新交易记录
                    self.trade_history_repo.close_trade(
                        trade_id=open_trade.id,
                        exit_price=exit_price,
                        pnl_usd=pnl_usd,
                        pnl_percent=pnl_percent,
                        fee_paid=result.fee,
                    )
                    logger.info(f"📝 Trade closed: {symbol} PnL: ${pnl_usd:.2f} ({pnl_percent:.2f}%)")
                except Exception as e:
                    logger.error(f"❌ Failed to update trade: {e}")
            
            return exec_result
        else:
            return ExecutionResult(
                symbol=symbol,
                action=decision.action,
                status="failed",
                message=result.error or "Unknown error",
            )
