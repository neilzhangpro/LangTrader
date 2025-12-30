# packages/langtrader_core/graph/nodes/risk_monitor.py
"""
风险监控节点
在交易执行前进行动态风险验证
"""
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import State, ExecutionResult
from langtrader_core.services.risk_monitor import RiskMonitor
from langtrader_core.utils import get_logger

logger = get_logger("risk_monitor_node")


class RiskMonitorNode(NodePlugin):
    """风险监控节点（在执行前验证）"""
    
    metadata = NodeMetadata(
        name="risk_monitor",
        display_name="Risk Monitor",
        version="1.0.0",
        author="LangTrader official",
        description="动态风险管理和验证",
        category="risk",
        tags=["risk", "monitor", "validation"],
        insert_after="decision",
        suggested_order=6,
        auto_register=True
    )
    
    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        
        # 从 bot config 读取风险限制
        risk_limits = config.get('risk_limits') if config else {
            "max_total_exposure_pct": 0.8,
            "max_consecutive_losses": 5,
            "max_single_symbol_pct": 0.3
        }
        
        self.risk_monitor = RiskMonitor(
            risk_limits=risk_limits,
            trade_history_repo=context.trade_history_repo if context else None
        )
    
    async def run(self, state: State) -> State:
        """对所有开仓决策进行风险验证"""
        
        logger.info(f"🛡️ Running risk validation on {len(state.runs)} decisions")
        
        for symbol, run_record in state.runs.items():
            if not run_record.decision:
                continue
            
            decision = run_record.decision
            
            # 只对开仓决策进行验证
            if decision.action not in ("open_long", "open_short"):
                continue
            
            # 执行风险验证
            validation = self.risk_monitor.validate_new_position(
                state,
                symbol,
                decision.position_size_usd
            )
            
            if not validation["approved"]:
                logger.warning(
                    f"❌ {symbol}: Risk validation FAILED - {validation['reasons']}"
                )
                
                # 修改决策为 wait
                decision.action = "wait"
                decision.reasons.extend([
                    "🚨 RISK LIMIT EXCEEDED:",
                    *validation["reasons"]
                ])
                
                # 创建拒绝执行结果
                run_record.execution = ExecutionResult(
                    symbol=symbol,
                    action="wait",
                    status="skipped",
                    message=f"Risk validation failed: {'; '.join(validation['reasons'])}"
                )
            else:
                logger.info(f"✅ {symbol}: Risk validation PASSED")
        
        return state

