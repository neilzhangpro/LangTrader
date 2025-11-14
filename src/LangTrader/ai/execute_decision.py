from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from src.LangTrader.utils import logger


class ExecuteDecision:
    def __init__(self,config):
        self.hyperliquid = hyperliquidAPI()
        self.config = config
        self.db = config.db
        self.symbols = config.symbols
    
    def _update_decision(self, decision_id):
        self.db.execute(
        """
        UPDATE decisions
        SET executed = TRUE
        WHERE id = %s
        """,
        (decision_id,),
        )

    def _update_position(
        self,
        state,
        object_state,
        direction,
        order_result,
        position_snapshot=None,
    ):
        logger.info("-----Start Update Position------")
        trader_id = state["trader_id"]
        decision_id = state["decision_id"]
        symbol = state["symbol"]
        side = state["side"]
        if direction == "open":
            account_balance = self.hyperliquid.get_account_balance()
            if not account_balance:
                logger.error("Failed to get account balance")
                return
            position = None
            asset_positions = account_balance.get("assetPositions") or []
            for asset in asset_positions:
                pos = asset.get("position") or {}
                coin = pos.get("coin")
                if coin == symbol:
                    position = pos
                    break
            if not position:
                logger.error("Failed to get real current position after opening")
                return

            entry_price = float(position.get("entryPx") or 0)
            quantity = float(position.get("szi") or 0)
            leverage = float((position.get("leverage") or {}).get("value") or 0)
            stop_loss_percent = self.config.risk_config.get("stop_loss_percent", 0.02)
            take_profit_percent = self.config.risk_config.get("take_profit_percent", 0.05)

            if quantity < 0:
                stop_loss = entry_price * (1 + stop_loss_percent)
                take_profit = entry_price * (1 - take_profit_percent)
            else:
                stop_loss = entry_price * (1 - stop_loss_percent)
                take_profit = entry_price * (1 + take_profit_percent)

            self.db.execute(
                """
                INSERT INTO positions (
                    trader_id, decision_id, symbol, side,
                    entry_price, quantity, leverage,
                    stop_loss, take_profit, realized_pnl,
                    status, opened_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    trader_id,
                    decision_id,
                    symbol,
                    side,
                    entry_price,
                    quantity,
                    leverage,
                    stop_loss,
                    take_profit,
                    0.0,
                    "open",
                ),
            )
        elif direction == "close":
            snapshot = position_snapshot or {}
            entry_price = float(snapshot.get("entry_price") or 0)
            quantity = float(snapshot.get("size") or 0)
            leverage = float(snapshot.get("leverage") or 0)

            filled_info = (
                ((order_result or {}).get("response") or {}).get("data") or {}
            ).get("statuses", [{}])[0].get("filled", {}) or {}
            exit_price_raw = filled_info.get("avgPx")
            try:
                exit_price = float(exit_price_raw)
            except (TypeError, ValueError):
                logger.error("Failed to parse exit price from order result, fallback to entry price")
                exit_price = entry_price

            realized_pnl = (exit_price - entry_price) * quantity

            existing_position = self.db.execute(
                """
                SELECT id FROM positions
                WHERE trader_id = %s AND symbol = %s AND status = 'open'
                ORDER BY opened_at DESC
                LIMIT 1
                """,
                (trader_id, symbol),
            )

            if not existing_position:
                logger.error(
                    "No open position record found for trader %s to update",
                    trader_id,
                )
                return

            position_id = existing_position[0]["id"]

            self.db.execute(
                """
                UPDATE positions
                SET
                    status = 'closed',
                    exit_price = %s,
                    realized_pnl = %s,
                    closed_at = NOW()
                WHERE id = %s
                """,
                (exit_price, realized_pnl, position_id),
            )


    def execute_decision(self, state):
        logger.info("-----Start Execute Decision------")
        symbol = state["symbol"]
        raw_action = state["action"] or ""
        raw_side = state["side"] or ""
        action = raw_action.upper()
        side = raw_side.lower()
        confidence = state["confidence"]
        leverage = state["leverage"]
        llm_analysis = state["llm_analysis"]
        decision_id = state["decision_id"]

        intent_map = {
            ("BUY", "long"): "OPEN_LONG",
            ("BUY", "short"): "OPEN_SHORT",
            ("SELL", "long"): "CLOSE_LONG",
            ("SELL", "short"): "CLOSE_SHORT",
        }
        intent = intent_map.get((action, side))
        if not intent:
            logger.warning(f"未识别的交易指令: action={action}, side={side}")
            return {**state, "executed": False}
        
        max_leverage = self.config.risk_config.get("max_leverage", 3)
        if leverage > max_leverage:
            logger.info("Leverage is greater than the max leverage")
            leverage = max_leverage
        if confidence < 0.6:
            logger.info("Confidence is less than 0.6, not executing decision")
            return {**state, "executed": False}
        
        symbol_key = symbol.upper()
        positions = state.get("current_positions") or {}
        position = positions.get(symbol_key) or positions.get(symbol)
        
        order_result = None
        position_snapshot = None
        direction = "open" if intent in {"OPEN_LONG", "OPEN_SHORT"} else "close"
        
        if intent in {"OPEN_LONG", "OPEN_SHORT"}:
            target_side = "long" if intent == "OPEN_LONG" else "short"
            account_state = state.get("account_balance")
            order_result = self.hyperliquid.open_position(
                symbol_key,
                target_side,
                leverage,
                confidence,
                account_state=account_state,
            )
        elif intent in {"CLOSE_LONG", "CLOSE_SHORT"}:
            if not position:
                logger.warning(f"尝试平仓 {symbol_key}，但当前无持仓信息，跳过执行")
                return {**state, "executed": False}
            position_side = position.get("side")
            if position_side != ("long" if intent == "CLOSE_LONG" else "short"):
                logger.warning(
                    f"{symbol_key} 当前仓位方向为 {position_side}，与指令 {intent} 不匹配"
                )
                return {**state, "executed": False}
            size = abs(float(position.get("size", 0)))
            position_snapshot = {
                "entry_price": position.get("entry_price"),
                "size": position.get("size"),
                "leverage": position.get("leverage"),
                "side": position_side,
            }
            order_result = self.hyperliquid.close_position(
                symbol_key,
                position_side,
                size,
            )
        if not order_result:
            logger.error("Failed to place order")
            return {**state, "executed": False}
        
        if decision_id:
            self._update_decision(decision_id)
        object_state =  {
            "action": raw_action,
            "side": raw_side,
            "confidence": confidence,
            "leverage": leverage,
            "llm_analysis": llm_analysis + f"\nOrder result: {order_result}",
            "executed": True,
            "executed_intent": intent
        }
        self._update_position(
            state,
            object_state,
            direction,
            order_result,
            position_snapshot=position_snapshot,
        )
        return {
            **state,
            **object_state
        }

