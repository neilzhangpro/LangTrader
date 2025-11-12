from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from src.LangTrader.utils import logger
from typing import List


class PositionAnalysis:
    def __init__(self):
        self.hyperliquid = hyperliquidAPI()

    def get_position_analysis(self, state):
        account_balance = self.hyperliquid.get_account_balance()
        if not account_balance:
            logger.error("无法获取账户持仓信息")
            return {
                **state,
                "position_data": "无法获取账户持仓信息",
                "current_positions": {},
                "account_balance": None
            }

        asset_positions = account_balance.get("assetPositions", []) or []
        margin_summary = account_balance.get("marginSummary", {}) or {}

        position_sections: List[str] = []
        current_positions = {}

        total_unrealized_pnl = 0.0
        total_margin_used = 0.0

        for asset_pos in asset_positions:
            position = asset_pos.get("position") or {}
            coin = position.get("coin")
            if not coin:
                continue

            try:
                size = float(position.get("szi", 0))
            except (TypeError, ValueError):
                size = 0.0

            if size == 0:
                continue

            try:
                entry_px = float(position.get("entryPx", 0))
            except (TypeError, ValueError):
                entry_px = 0.0

            try:
                position_value = float(position.get("positionValue", 0))
            except (TypeError, ValueError):
                position_value = 0.0

            mark_px = position_value / abs(size) if abs(size) > 0 else 0.0

            try:
                unrealized_pnl = float(position.get("unrealizedPnl", 0))
            except (TypeError, ValueError):
                unrealized_pnl = 0.0

            try:
                liquidation_px = float(position.get("liquidationPx", 0))
            except (TypeError, ValueError):
                liquidation_px = 0.0

            leverage_info = position.get("leverage", {}) or {}
            try:
                leverage_value = float(leverage_info.get("value", leverage_info or 0))
            except (TypeError, ValueError):
                leverage_value = 0.0

            try:
                margin_used = float(position.get("marginUsed", 0))
            except (TypeError, ValueError):
                margin_used = 0.0

            pnl_percentage = (unrealized_pnl / margin_used * 100) if margin_used > 0 else 0.0
            distance_to_liq = abs((mark_px - liquidation_px) / mark_px * 100) if mark_px > 0 else 0.0

            side = "long" if size > 0 else "short"

            current_positions[coin] = {
                "size": size,
                "side": side,
                "entry_price": entry_px,
                "current_price": mark_px,
                "unrealized_pnl": unrealized_pnl,
                "pnl_percentage": pnl_percentage,
                "leverage": leverage_value,
                "liquidation_price": liquidation_px,
                "distance_to_liquidation_pct": distance_to_liq,
                "margin_used": margin_used,
                "position_value": position_value
            }

            section = (
                f"持仓分析 - {coin}:\n"
                f"- 方向: {'做多' if side == 'long' else '做空'}\n"
                f"- 仓位大小: {abs(size):.4f} {coin}\n"
                f"- 入场价格: ${entry_px:.4f}\n"
                f"- 当前价格: ${mark_px:.4f}\n"
                f"- 未实现盈亏: ${unrealized_pnl:.2f} ({pnl_percentage:+.2f}%)\n"
                f"- 杠杆倍数: {leverage_value:.2f}x\n"
                f"- 强平价格: ${liquidation_px:.4f}\n"
                f"- 距离强平: {distance_to_liq:.2f}%\n"
                f"- 占用保证金: ${margin_used:.2f}\n"
                f"- 仓位价值: ${position_value:.2f}"
            )
            position_sections.append(section)

            total_unrealized_pnl += unrealized_pnl
            total_margin_used += margin_used

        if position_sections:
            positions_summary = "\n\n".join(position_sections)
            account_value = float(margin_summary.get("accountValue", 0) or 0)
            position_ratio = (total_margin_used / account_value * 100) if account_value > 0 else 0.0

            positions_summary += (
                "\n\n总体风险指标:\n"
                f"- 总未实现盈亏: ${total_unrealized_pnl:.2f}\n"
                f"- 总占用保证金: ${total_margin_used:.2f}\n"
                f"- 账户总价值: ${account_value:.2f}\n"
                f"- 仓位保证金占比: {position_ratio:.2f}%"
            )
        else:
            positions_summary = "当前无持仓"

        logger.info("-----End Position Analysis------")
        return {
                **state,
                "position_data": positions_summary,
                "current_positions": current_positions,
                "account_balance": account_balance
            }