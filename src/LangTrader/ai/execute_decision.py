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
        competition_id = state.get("competition_id")  # 🆕
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
                    trader_id, decision_id, competition_id, symbol, side,
                    entry_price, quantity, leverage,
                    stop_loss, take_profit, realized_pnl,
                    status, opened_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    trader_id,
                    decision_id,
                    competition_id,  # 🆕
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
    
    def _check_force_close(self, state):
        """
        检查是否触发强制止损/止盈
        
        Returns:
            如果触发强制风控，返回覆盖决策的字典
            如果未触发，返回None
        """
        current_positions = state.get("current_positions", {})
        
        if not current_positions:
            return None
        
        risk_config = self.config.risk_config
        stop_loss_pct = risk_config.get("stop_loss_percent", 0.05) * 100
        take_profit_pct = risk_config.get("take_profit_percent", 0.12) * 100
        
        # 检查每个持仓
        for symbol, pos in current_positions.items():
            pnl_pct = pos.get("pnl_percentage", 0)
            side = pos.get("side", "")
            
            # 触发止损
            if pnl_pct <= -stop_loss_pct:
                logger.warning(f"🚨🚨🚨 {symbol} 触发强制止损！亏损 {pnl_pct:.2f}%")
                logger.warning(f"💀 强制执行: SELL + {side}")
                
                return {
                    "action": "SELL",
                    "side": side,
                    "symbol": symbol,
                    "confidence": 0.99,  # 强制执行，高置信度
                    "leverage": 1,
                    "executed_intent": f"强制止损：{symbol} {side}仓亏损 {pnl_pct:.2f}%，已达止损线-{stop_loss_pct:.0f}%",
                    "llm_analysis": f"系统强制止损：{symbol} {side}仓亏损{pnl_pct:.2f}%，触发止损规则（-{stop_loss_pct:.0f}%）。保护本金，立即平仓。"
                }
            
            # 触发止盈（建议，不强制）
            elif pnl_pct >= take_profit_pct:
                logger.info(f"💰 {symbol} 达到止盈目标！盈利 {pnl_pct:.2f}%")
                logger.info(f"💡 建议平仓锁定利润，或AI可选择继续持有")
                # 不覆盖AI决策，只记录
        
        return None

    def execute_decision(self, state):
        logger.info("-----Start Execute Decision------")
        
        # 🚨 优先检查强制止损止盈
        force_close_result = self._check_force_close(state)
        if force_close_result:
            # 如果触发强制止损止盈，覆盖AI决策
            state.update(force_close_result)
            logger.warning(f"🚨 触发强制风控：{force_close_result.get('executed_intent', '')}")
        
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
            
            logger.info(f"🚀 准备开仓: {symbol_key} {target_side}")
            
            order_result = self.hyperliquid.open_position(
                symbol_key,
                target_side,
                leverage,
                confidence,
                account_state=account_state,
            )
            
            # 添加详细调试信息
            logger.info(f"📊 order_result 类型: {type(order_result)}")
            logger.info(f"📊 order_result 是否为None: {order_result is None}")
            
            if order_result:
                logger.info(f"📊 order_result keys: {list(order_result.keys()) if isinstance(order_result, dict) else 'Not a dict'}")
                logger.info(f"📊 order_result 完整内容: {order_result}")
            
            if order_result is not None:
                logger.info(f"🛡️ 开仓有返回结果，立即设置止损止盈保护...")
                protection_ok = self._set_stop_loss_take_profit(symbol_key, target_side, order_result)
                if not protection_ok:
                    logger.error(f"❌ {symbol_key} 止损/止盈保护设置失败，系统将撤销本次开仓")
                    self._handle_protection_failure(symbol_key)
                    failure_analysis = llm_analysis + "\n⚠️ 止损/止盈保护下单失败，本次交易已被系统强制关闭。"
                    return {
                        **state,
                        "executed": False,
                        "executed_intent": "FAILED_PROTECTION",
                        "llm_analysis": failure_analysis
                    }
            else:
                logger.warning(f"⚠️ 开仓失败或返回None，跳过止损止盈设置")
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
    
    def _extract_entry_price(self, order_result):
        """从订单结果中提取入场价格"""
        logger.info(f"🔍 _extract_entry_price 接收到的数据类型: {type(order_result)}")
        
        try:
            if isinstance(order_result, dict):
                logger.info(f"📊 order_result keys: {list(order_result.keys())}")
                
                response = order_result.get("response", {})
                logger.info(f"📊 response 类型: {type(response)}")
                
                if isinstance(response, dict):
                    logger.info(f"📊 response keys: {list(response.keys())}")
                    data = response.get("data", {})
                    logger.info(f"📊 data: {data}")
                    
                    statuses = data.get("statuses", [])
                    logger.info(f"📊 statuses 数量: {len(statuses)}")
                    
                    if statuses:
                        logger.info(f"📊 第一个status: {statuses[0]}")
                        filled = statuses[0].get("filled", {})
                        logger.info(f"📊 filled: {filled}")
                        avg_px = filled.get("avgPx")
                        logger.info(f"📊 avgPx: {avg_px}")
                        
                        if avg_px:
                            price = float(avg_px)
                            logger.info(f"✅ 成功提取入场价格: ${price:,.2f}")
                            return price
            
            logger.error("❌ 无法从订单结果中提取入场价格")
            logger.error(f"   order_result 完整内容: {order_result}")
            
        except Exception as e:
            logger.error(f"❌ 提取入场价格异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return None
    
    def _set_stop_loss_take_profit(self, symbol, side, order_result):
        """
        开仓后立即设置止损止盈
        
        Args:
            symbol: 币种
            side: 仓位方向 long/short
            order_result: 开仓订单结果
        """
        logger.info(f"🔧 进入 _set_stop_loss_take_profit 方法")
        logger.info(f"   symbol: {symbol}, side: {side}")
        
        try:
            # 提取入场价格
            logger.info(f"🔍 开始提取入场价格...")
            entry_price = self._extract_entry_price(order_result)
            
            logger.info(f"📊 提取到的入场价格: {entry_price}")
            
            if not entry_price:
                logger.error(f"❌ 无法获取 {symbol} 入场价格，止损止盈设置失败")
                logger.error(f"   order_result: {order_result}")
                logger.warning("⚠️ 仓位无保护，建议手动设置或依赖强制风控检查")
                return False
            
            # 获取风控配置
            risk_config = self.config.risk_config
            stop_loss_pct = risk_config.get("stop_loss_percent", 0.05)
            take_profit_pct = risk_config.get("take_profit_percent", 0.12)
            
            # 计算止损止盈价格
            if side == "long":
                stop_loss_price = entry_price * (1 - stop_loss_pct)
                take_profit_price = entry_price * (1 + take_profit_pct)
            else:  # short
                stop_loss_price = entry_price * (1 + stop_loss_pct)
                take_profit_price = entry_price * (1 - take_profit_pct)
            
            # ✅ 价格精度处理：根据币种价格范围取整
            stop_loss_price = self._round_price_for_symbol(symbol, stop_loss_price)
            take_profit_price = self._round_price_for_symbol(symbol, take_profit_price)
            
            logger.info(f"📊 {symbol} {side}仓位保护设置:")
            logger.info(f"   入场价: ${entry_price:,.2f}")
            logger.info(f"   止损价: ${stop_loss_price:,.2f} (-{stop_loss_pct*100:.0f}%)")
            logger.info(f"   止盈价: ${take_profit_price:,.2f} (+{take_profit_pct*100:.0f}%)")
            
            # 设置止损单
            stop_result = self.hyperliquid.place_stop_loss_order(
                coin_name=symbol,
                side=side,
                trigger_price=stop_loss_price
            )
            
            stop_success = bool(stop_result)
            if stop_success:
                logger.info(f"✅ {symbol} 止损单设置成功")
            else:
                logger.error(f"❌ {symbol} 止损单设置失败")
            
            # 设置止盈单
            tp_result = self.hyperliquid.place_take_profit_order(
                coin_name=symbol,
                side=side,
                trigger_price=take_profit_price
            )
            
            tp_success = bool(tp_result)
            if tp_success:
                logger.info(f"✅ {symbol} 止盈单设置成功")
            else:
                logger.error(f"❌ {symbol} 止盈单设置失败")
            
            # 总结
            if stop_success and tp_success:
                logger.info(f"🎉 {symbol} 仓位保护完成！")
                logger.info(f"   ✅ 止损单: ${stop_loss_price:,.2f}")
                logger.info(f"   ✅ 止盈单: ${take_profit_price:,.2f}")
                logger.info(f"   🔒 24/7自动保护，即使程序停止也有效")
            elif stop_success:
                logger.warning(f"⚠️ {symbol} 仅止损单成功，止盈单失败")
            else:
                logger.error(f"❌ {symbol} 止损止盈设置失败，仓位无保护！")
                logger.warning(f"   请依赖程序的强制风控检查（每次运行时检查）")
            
            return bool(stop_success and tp_success)
        except Exception as e:
            logger.error(f"❌ 设置止损止盈失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _handle_protection_failure(self, symbol: str) -> bool:
        """
        止损/止盈单未成功设置时，撤销相关订单并强制平仓，避免裸奔仓位
        """
        try:
            symbol_key = symbol.upper()
            logger.warning(f"⚠️ {symbol_key} 保护单缺失，启动紧急平仓流程")
            
            account_balance = self.hyperliquid.get_account_balance()
            if not account_balance:
                logger.error("❌ 无法获取账户信息，紧急平仓失败")
                return False
            
            positions = account_balance.get("assetPositions", []) or []
            for asset in positions:
                position = asset.get("position") or {}
                if position.get("coin") != symbol_key:
                    continue
                
                size = float(position.get("szi") or 0)
                if size == 0:
                    continue
                
                position_side = "long" if size > 0 else "short"
                quantity = abs(size)
                
                logger.info(f"🛑 {symbol_key} 当前仓位 {position_side} {quantity}，立即撤单并平仓")
                self.hyperliquid.cancel_all_orders_for_coin(symbol_key)
                close_result = self.hyperliquid.close_position(symbol_key, position_side, quantity)
                
                if close_result:
                    logger.info(f"✅ {symbol_key} 裸奔仓位已强制平仓")
                    return True
                
                logger.error(f"❌ {symbol_key} 紧急平仓返回为空，需人工干预")
                return False
            
            logger.warning(f"⚠️ 未在账户中找到 {symbol_key} 仓位，可能已被交易所关闭")
            return False
        except Exception as e:
            logger.error(f"❌ 紧急平仓流程异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _round_price_for_symbol(self, symbol: str, price: float) -> float:
        """
        根据币种价格范围将价格舍入到合适的精度
        
        Hyperliquid要求止损止盈价格必须符合tick size
        
        Args:
            symbol: 币种符号
            price: 原始价格
            
        Returns:
            舍入后的价格
        """
        try:
            # 根据价格范围确定精度
            if price >= 1000:  # BTC, ETH等高价币
                # 取整到整数
                rounded = round(price, 0)
                logger.debug(f"💡 高价币 {symbol}: ${price:.2f} → ${rounded:.0f}")
            elif price >= 100:  # BNB, SOL等中价币
                # 保留1位小数
                rounded = round(price, 1)
                logger.debug(f"💡 中价币 {symbol}: ${price:.2f} → ${rounded:.1f}")
            elif price >= 1:  # 低价币
                # 保留2位小数
                rounded = round(price, 2)
                logger.debug(f"💡 低价币 {symbol}: ${price:.2f} → ${rounded:.2f}")
            else:  # 极低价币
                # 保留4位小数
                rounded = round(price, 4)
                logger.debug(f"💡 极低价币 {symbol}: ${price:.4f} → ${rounded:.4f}")
            
            return rounded
            
        except Exception as e:
            logger.error(f"价格舍入失败: {e}")
            # 默认取整
            return round(price, 0)

