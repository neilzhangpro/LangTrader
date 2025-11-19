import json
from decimal import Decimal
from src.LangTrader.utils import logger
from hyperliquid.info import Info
from hyperliquid.utils import constants
from hyperliquid.exchange import Exchange
import eth_account
from eth_account.signers.local import LocalAccount


class hyperliquidAPI:
    """ This class is used to interact with the hyperliquid API"""
    def __init__(self, config_path:str = "config.json"):
        #loading config
        with open(config_path,"r") as f:
            config = json.load(f)
        self.account_address = config["account_address"]
        self.secret_key = config["secret_key"]
        self.account:LocalAccount = eth_account.Account.from_key(self.secret_key)
        #ues mainnet api
        self.info = Info(constants.MAINNET_API_URL, skip_ws=True)
        #use testnet api
        #self.info_testnet = Info(constants.TESTNET_API_URL, skip_ws=True)
        self.contract_balance = self.get_account_balance()
        self.spot_balance = self.get_account_balance()
        #init exchange
        self.exchange = Exchange(
            self.account,
            base_url=constants.MAINNET_API_URL,
            account_address=self.account_address,
            perp_dexs=None
        )
        self.contract_positions = []

    def get_account_balance(self):
        """Get the accound balance of the account"""
        try:
            #contract balance
            user_state = self.info.user_state(self.account_address)
            logger.info(f"Contract account balance: {user_state}")
            self.contract_balance = user_state
            #spot balance
            spot_user_state = self.info.spot_user_state(self.account_address)
            logger.info(f"Spot account balance: {spot_user_state}")
            self.spot_balance = spot_user_state
            return user_state
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return None
    

    DEFAULT_SLIPPAGE = 0.01
    SIZE_PRECISION = 6

    def calculate_buy_size(
        self,
        coin_name: str,
        leverage: int = 1,
        slippage: float = DEFAULT_SLIPPAGE,
        confidence: float = 0.95,
        min_notional: float = 1.0,
        account_state: dict | None = None,
    ):
        """
        估算下单规模，返回字典；若余额或数据不足则返回 None。

        Args:
            coin_name: 要交易的币种（大小写不限）
            leverage: 目标杠杆倍数
            slippage: 预估滑点（用于日志提示，不参与数量计算）
            confidence: 安全系数；越小预留越多保证金
            min_notional: 最小允许的名义成交额（USD），默认 1.0；可视需要调优
        """
        coin_name = coin_name.upper()

        try:
            # ==== 获取最新账户信息 ====
            account_state = account_state or self.get_account_balance()
            if not account_state:
                logger.error("无法刷新账户余额，取消下单计算")
                return None

            margin_summary = account_state.get("marginSummary") or {}
            withdrawable = float(account_state.get("withdrawable") or margin_summary.get("withdrawable", 0) or 0)
            if withdrawable <= 0:
                logger.warning("账户可用保证金为 0，无法开仓")
                return None

            # ==== 获取中间价 ====
            all_mids = self.info.all_mids()
            mid_price = float(all_mids.get(coin_name, 0))
            if mid_price <= 0:
                logger.error(f"{coin_name} 当前无法获取价格，all_mids: {all_mids}")
                return None

            # ==== 获取单币种可用额度 ====
            available_to_trade = withdrawable / mid_price
            if hasattr(self.info, "active_asset_data"):
                try:
                    active_asset = self.info.active_asset_data(self.account_address, coin_name)
                    available_list = active_asset.get("availableToTrade") or ["0", "0"]
                    available_to_trade = float(available_list[0])
                except Exception as exc:
                    logger.warning(f"获取 {coin_name} active_asset_data 失败，退化为 withdrawable 估算: {exc}")

            # ==== 计算最大名义价值 ====
            max_notional = withdrawable * leverage * confidence
            if max_notional < min_notional:
                logger.info(
                    f"{coin_name} 最大可用名义价值 {max_notional:.4f} < 最小成交额 {min_notional:.4f}，余额不足"
                )
                return None

            # ==== 名义价值换算为数量，并与 available_to_trade 取最小值 ====
            max_size_from_notional = max_notional / mid_price
            max_size = min(max_size_from_notional, available_to_trade)

            # ==== 根据交易所 meta 信息截断至合法步进 ====
            max_size_decimal = Decimal(str(max_size))
            available_decimal = Decimal(str(available_to_trade))
            size_increment: Decimal | None = None
            min_order_size: Decimal | None = None

            try:
                meta = self.info.meta()
                universe = meta.get("universe", [])
                asset_meta = next(
                    (asset for asset in universe if asset.get("name", "").upper() == coin_name),
                    None,
                )
                if asset_meta:
                    meta_info = asset_meta.get("meta") or {}

                    raw_increment = (
                        asset_meta.get("sizeIncrement")
                        or asset_meta.get("szIncrement")
                        or asset_meta.get("stepSize")
                        or meta_info.get("sizeIncrement")
                        or meta_info.get("szIncrement")
                        or meta_info.get("stepSize")
                    )
                    if raw_increment:
                        size_increment = Decimal(str(raw_increment))
                    else:
                        sz_decimals = (
                            asset_meta.get("szDecimals")
                            or meta_info.get("szDecimals")
                        )
                        if sz_decimals is not None:
                            try:
                                size_increment = Decimal("1") / (Decimal(10) ** int(sz_decimals))
                            except Exception as decimals_exc:
                                logger.warning(f"{coin_name} szDecimals 解析失败: {decimals_exc}")

                    raw_min_size = (
                        asset_meta.get("minProvideSz")
                        or asset_meta.get("minSize")
                        or asset_meta.get("minOrderSize")
                        or meta_info.get("minProvideSz")
                        or meta_info.get("minSize")
                        or meta_info.get("minOrderSize")
                    )
                    if raw_min_size:
                        min_order_size = Decimal(str(raw_min_size))
            except Exception as exc:
                logger.warning(f"获取 {coin_name} meta 信息失败，使用默认精度：{exc}")

            if size_increment and size_increment > 0:
                try:
                    available_decimal = (available_decimal // size_increment) * size_increment
                    max_size_decimal = (max_size_decimal // size_increment) * size_increment
                    logger.debug(
                        f"{coin_name} 步进 {size_increment} 最小量 {min_order_size} 调整后数量 {max_size_decimal}"
                    )
                except Exception as exc:
                    logger.warning(f"{coin_name} 步进截断失败，使用默认精度：{exc}")
                    size_increment = None

            if not size_increment:
                available_decimal = Decimal(
                    str(round(float(available_decimal), self.SIZE_PRECISION))
                )
                max_size_decimal = Decimal(
                    str(round(float(max_size_decimal), self.SIZE_PRECISION))
                )

            if min_order_size and min_order_size > 0 and max_size_decimal < min_order_size:
                logger.info(
                    f"{coin_name} 调整到步进后的数量 {max_size_decimal} 低于最小下单量 {min_order_size}"
                )
                return None

            if max_size_decimal <= 0:
                logger.info(f"{coin_name} 经过精度裁剪后数量为 0，取消下单")
                return None

            max_size = float(max_size_decimal)
            available_to_trade = float(available_decimal)

            if max_size * mid_price < min_notional:
                logger.info(
                    f"{coin_name} 名义价值 {max_size * mid_price:.4f} 仍低于最小成交额 {min_notional:.4f}"
                )
                return None

            result = {
                "coin_name": coin_name,
                "price": mid_price,
                "max_buy_size": max_size,
                "max_notional": max_size * mid_price,
                "withdrawable": withdrawable,
                "available_to_trade": available_to_trade,
                "leverage": leverage,
                "confidence": confidence,
                "slippage": slippage,
            }

            logger.info(
                f"买入估算结果: {result}"
            )
            return result

        except Exception as e:
            logger.error(f"Error calculating buy size: {e}")
            logger.exception(e)
            return None

    def open_position(
        self,
        coin_name: str,
        side: str,
        leverage: int,
        confidence: float,
        slippage: float = DEFAULT_SLIPPAGE,
        account_state: dict | None = None,
    ):
        """按方向开仓，side 可取 long/short"""
        coin_name = coin_name.upper()
        side = side.lower()
        if side not in {"long", "short"}:
            logger.error(f"无效的 side: {side}")
            return None

        try:
            plan = self.calculate_buy_size(
                coin_name,
                leverage=leverage,
                slippage=slippage,
                confidence=confidence,
                account_state=account_state,
            )
            if not plan:
                logger.warning("余额或名义价值不足，无法开仓")
                return None

            size = plan["max_buy_size"]
            if size <= 0:
                logger.warning("计算得到的下单数量为 0，取消开仓")
                return None

            logger.info(
                f"📝 Opening {side} position: {coin_name} size={size} @ {leverage}x (conf: {confidence:.0%})"
            )

            leverage_result = self.exchange.update_leverage(leverage, coin_name, True)
            logger.info(f"Leverage set: {leverage_result}")

            is_buy = side == "long"
            order_result = self.exchange.market_open(
                coin_name,
                is_buy=is_buy,
                sz=size,
                slippage=slippage,
            )
            logger.info(f"✅ 开仓成功: {order_result}")
            return order_result

        except Exception as exc:
            logger.error(f"❌ 开仓失败: {exc}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def close_position(
        self,
        coin_name: str,
        side: str,
        size: float,
        slippage: float = DEFAULT_SLIPPAGE,
    ):
        """按方向平仓，size > 0"""
        coin_name = coin_name.upper()
        side = side.lower()
        if side not in {"long", "short"}:
            logger.error(f"无效的 side: {side}")
            return None

        if size <= 0:
            logger.warning(f"{coin_name} {side} 仓位数量 <= 0，跳过平仓")
            return None

        try:
            logger.info(f"📝 Closing {side} position: {coin_name} size={size}")
            order_result = self.exchange.market_close(
                coin_name,
                sz=size,
                slippage=slippage,
            )
            logger.info(f"✅ 平仓成功: {order_result}")
            return order_result
        except Exception as exc:
            logger.error(f"❌ 平仓失败: {exc}")
            import traceback
            logger.error(traceback.format_exc())
            return None

        
    def test_order(self,coin_name:str):
        """Set a test order"""
        try:
            #calculate the buy size
            coin_name = coin_name.upper()
            leverage = 5
            #set leverage
            logger.info(f"Setting leverage to {leverage}")
            leverage_result = self.exchange.update_leverage(
                leverage,
                coin_name,
                True, # use cross margin
            )
            logger.info(f"Leverage result: {leverage_result}")
            #calculate the buy size
            buy_size = self.calculate_buy_size(coin_name,5)
            if buy_size is None:
                logger.info("Insufficent balance for buying")
                return None
            logger.info(f"Buying {buy_size['max_buy_size']} {buy_size['coin_name']} with leverage {buy_size['leverage']}")
            #use the market order
            order_result = self.exchange.market_open(
                coin_name,
                True,
                buy_size["max_buy_size"],
                None,
                0.01
            )
            logger.info(f"Test order result: {order_result}")
            return order_result
        except Exception as e:
            logger.error(f"Error setting test order: {e}")
            return None
    
    def close_all_positions(self,order_type:str = "market", limit_price_offset: float = 0.5,limit_price:float = None, tif: str="Gtc"):
        """
        Close all postions
        Args:
            order_type: str = "market",
            limit_price_offset: float = 0.5,
            limit_price: float = None,
            tif: str="Gtc"
                - "Gtc": until the order is executed
                - "Ioc": immediate or cancel
                - "Alo": Add liquidity only
        """
        #should update the balance anyway
        self.contract_balance = self.get_account_balance()
        self.spot_balance = self.get_account_balance()
        try:
            #get all postion
            postions = self.contract_balance["assetPositions"]
            if not postions:
                logger.info("No postions to close")
                return
            
            logger.info(f"Closing {len(postions)} positions")
            logger.info(f"Preparing to {'limit' if order_type == 'limit' else 'market'} order with {limit_price_offset} offset and {tif} tif")

            #get limit price
            all_mids = self.info.all_mids() if order_type == "limit" else {}

            for position in postions:
                pos = position.get("position",{})
                coin = pos.get("coin")
                szi = float(pos.get("szi","0"))
                size = abs(szi)

                if size == 0:
                    logger.info(f"Position {coin} is already closed")
                    continue

                #judge long or short position
                is_long = szi > 0
                
                logger.info(f"Closing {coin} position with size {size}")
                 
                if order_type == "market":
                    #close by market order
                    result = self.exchange.market_close(
                        coin,
                        size,
                        slippage=0.01
                    )
                else:
                    #close by limit order
                    is_buy = not is_long
                    current_price = float(all_mids.get(coin,0))
                    if current_price == 0:
                        ValueError(f"There is no price for {coin}");
                        continue

                    if limit_price is not None:
                        final_price = limit_price
                        logger.info(f"Using provided limit price: {final_price}")
                    else:
                        #calulate the limit price
                        if is_long:
                            final_price = current_price * (1 - limit_price_offset / 100)
                        else:
                            final_price = current_price * (1 + limit_price_offset / 100)
                        final_price = round(final_price,3)
                        logger.info(f"Limit price for {coin} is {final_price}")
                    result = self.exchange.order(
                        coin,
                        is_buy,
                        size,
                        final_price,
                        {"limit":{"tif":tif}},
                        reduce_only=True
                    )
                logger.info(f"Closed result: {result}")
            
            return True
        except Exception as e:
            logger.error(f"⚠️ Error closing positions: {e}")
            return None
    

    def _get_asset_index(self,coin_name:str):
        """Get the index of universe """
        try:
            meta = self.info.meta()
            universa = meta.get("universe",[])

            for idx, asset in enumerate(universa):
                if asset.get("name") == coin_name:
                    return idx
            
            raise ValueError(f"Asset {coin_name} not found in universe")
        except Exception as e:
            logger.error(f"Error getting asset index: {e}")
            return None
    
    def place_stop_loss_order(
        self,
        coin_name: str,
        side: str,
        trigger_price: float
    ):
        """
        设置止损单（使用trigger订单 + positionTpsl分组）
        
        Args:
            coin_name: 币种名称，如 'BTC'
            side: 当前持仓方向 'long' 或 'short'
            trigger_price: 止损触发价格
        
        Returns:
            订单结果
        """
        coin_name = coin_name.upper()
        
        try:
            # 获取当前仓位信息
            account_balance = self.get_account_balance()
            if not account_balance:
                logger.error("无法获取账户信息")
                return None
            
            # 找到对应仓位
            positions = account_balance.get("assetPositions", [])
            position_size = 0
            
            for asset in positions:
                pos = asset.get("position", {})
                if pos.get("coin") == coin_name:
                    position_size = abs(float(pos.get("szi", 0)))
                    break
            
            if position_size == 0:
                logger.warning(f"{coin_name} 无持仓，跳过止损单设置")
                return None
            
            logger.info(f"🛡️ 设置 {coin_name} 止损单")
            logger.info(f"   持仓方向: {side}")
            logger.info(f"   触发价格: ${trigger_price:,.2f}")
            logger.info(f"   仓位大小: {position_size}")
            
            # 止损方向：long仓用sell止损，short仓用buy止损
            is_buy = (side.lower() == "short")
            logger.info(f"   止损方向: {'buy' if is_buy else 'sell'}")
            
            # 使用SDK的order方法设置trigger订单
            logger.info(f"🔧 调用 exchange.order() 设置止损单...")
            logger.info(f"   参数: coin={coin_name}, is_buy={is_buy}, sz={position_size}")
            logger.info(f"   order_type: trigger, triggerPx={trigger_price}, tpsl=sl")
            
            # ✅ 使用位置参数（参考第421行的正确用法）
            order_result = self.exchange.order(
                coin_name,      # 位置参数1：币种
                is_buy,         # 位置参数2：买卖方向
                position_size,  # 位置参数3：数量
                trigger_price,  # 位置参数4：价格
                {"trigger": {   # 位置参数5：订单类型
                    "triggerPx": trigger_price,  # ✅ 直接传float，不要转字符串
                    "isMarket": True,  # 触发后使用市价
                    "tpsl": "sl"  # 止损单
                }},
                reduce_only=True  # 关键字参数
            )
            
            logger.info(f"📥 止损单返回结果: {order_result}")
            
            # 检查是否有错误
            if isinstance(order_result, dict):
                response = order_result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses and isinstance(statuses[0], dict):
                    if "error" in statuses[0]:
                        error_msg = statuses[0]["error"]
                        logger.error(f"❌ 止损单设置失败: {error_msg}")
                        return None
                    elif "resting" in statuses[0]:
                        oid = statuses[0]["resting"].get("oid")
                        logger.info(f"✅ 止损单设置成功, oid={oid}")
                        return order_result
            
            logger.info(f"✅ 止损单已提交")
            return order_result
            
        except Exception as e:
            logger.error(f"❌ 设置止损单失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def place_take_profit_order(
        self,
        coin_name: str,
        side: str,
        trigger_price: float
    ):
        """
        设置止盈单（使用trigger订单 + positionTpsl分组）
        
        Args:
            coin_name: 币种名称
            side: 当前持仓方向
            trigger_price: 止盈触发价格
        """
        coin_name = coin_name.upper()
        
        try:
            # 获取仓位信息
            account_balance = self.get_account_balance()
            if not account_balance:
                return None
            
            positions = account_balance.get("assetPositions", [])
            position_size = 0
            
            for asset in positions:
                pos = asset.get("position", {})
                if pos.get("coin") == coin_name:
                    position_size = abs(float(pos.get("szi", 0)))
                    break
            
            if position_size == 0:
                logger.warning(f"{coin_name} 无持仓，跳过止盈单设置")
                return None
            
            logger.info(f"🎯 设置 {coin_name} 止盈单")
            logger.info(f"   触发价格: ${trigger_price:,.2f}")
            logger.info(f"   仓位大小: {position_size}")
            
            is_buy = (side.lower() == "short")
            logger.info(f"   止盈方向: {'buy' if is_buy else 'sell'}")
            
            logger.info(f"🔧 调用 exchange.order() 设置止盈单...")
            logger.info(f"   参数: coin={coin_name}, is_buy={is_buy}, sz={position_size}")
            logger.info(f"   order_type: trigger, triggerPx={trigger_price}, tpsl=tp")
            
            # ✅ 使用位置参数
            order_result = self.exchange.order(
                coin_name,      # 位置参数1：币种
                is_buy,         # 位置参数2：买卖方向
                position_size,  # 位置参数3：数量
                trigger_price,  # 位置参数4：价格
                {"trigger": {   # 位置参数5：订单类型
                    "triggerPx": trigger_price,  # ✅ 直接传float，不要转字符串
                    "isMarket": False,  # 止盈用限价更好
                    "tpsl": "tp"  # 止盈单
                }},
                reduce_only=True  # 关键字参数
            )
            
            logger.info(f"📥 止盈单返回结果: {order_result}")
            
            # 检查是否有错误
            if isinstance(order_result, dict):
                response = order_result.get("response", {})
                data = response.get("data", {})
                statuses = data.get("statuses", [])
                
                if statuses and isinstance(statuses[0], dict):
                    if "error" in statuses[0]:
                        error_msg = statuses[0]["error"]
                        logger.error(f"❌ 止盈单设置失败: {error_msg}")
                        return None
                    elif "resting" in statuses[0]:
                        oid = statuses[0]["resting"].get("oid")
                        logger.info(f"✅ 止盈单设置成功, oid={oid}")
                        return order_result
            
            logger.info(f"✅ 止盈单已提交")
            return order_result
            
        except Exception as e:
            logger.error(f"❌ 设置止盈单失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def get_open_orders(self, coin_name: str = None):
        """
        获取未完成订单
        
        Args:
            coin_name: 币种（可选）
        """
        try:
            orders = self.info.open_orders(self.account_address)
            
            if coin_name:
                coin_name = coin_name.upper()
                filtered = [o for o in orders if o.get("coin") == coin_name]
                logger.info(f"📋 {coin_name} 有 {len(filtered)} 个未完成订单")
                return filtered
            
            logger.info(f"📋 总共有 {len(orders)} 个未完成订单")
            return orders
            
        except Exception as e:
            logger.error(f"获取订单失败: {e}")
            return []
    
    def cancel_order_by_oid(self, coin_name: str, oid: int):
        """
        根据订单ID取消订单
        
        Args:
            coin_name: 币种
            oid: 订单ID
        """
        coin_name = coin_name.upper()
        
        try:
            cancel_result = self.exchange.cancel(coin_name, oid)
            
            logger.info(f"✅ 已取消订单: {coin_name} oid={oid}")
            return cancel_result
            
        except Exception as e:
            logger.error(f"取消订单失败: {e}")
            return None
    
    def cancel_all_orders_for_coin(self, coin_name: str):
        """取消某个币种的所有未完成订单"""
        
        coin_name = coin_name.upper()
        
        try:
            open_orders = self.get_open_orders(coin_name)
            
            if not open_orders:
                logger.info(f"{coin_name} 无未完成订单")
                return True
            
            logger.info(f"📋 准备取消 {coin_name} 的 {len(open_orders)} 个订单")
            
            for order in open_orders:
                oid = order.get("oid")
                if oid:
                    self.cancel_order_by_oid(coin_name, oid)
            
            logger.info(f"✅ {coin_name} 所有订单已取消")
            return True
            
        except Exception as e:
            logger.error(f"批量取消订单失败: {e}")
            return False