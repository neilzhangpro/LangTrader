"""
Trader - 全面的订单管理（基于 CCXT Pro）

支持功能：
- 创建订单（市价/限价/止损/止盈）
- 修改订单
- 取消订单
- 一键开仓（主订单 + 止损 + 止盈）
- 平仓
- 查询订单/持仓

错误处理：
- 利用 CCXT 内置异常类型进行精确错误分类
- 参考: https://docs.ccxt.com/README?id=error-handling
- 使用 fetch_status() 检查交易所状态
"""
import ccxt.pro as ccxtpro
import ccxt  # 导入 CCXT 基础模块用于异常类型
from datetime import datetime
from typing import Optional, Dict, List, Any

from langtrader_core.graph.state import (
    Account, Position, OrderResult, OpenPositionResult,
    OrderType, OrderSide, PositionSide
)
from langtrader_core.services.fee_calculator import FeeCalculator
from langtrader_core.utils import get_logger

logger = get_logger("trader")


# ==================== CCXT 错误分类 ====================
# 参考: https://docs.ccxt.com/README?id=error-handling
#
# BaseError
# ├── ExchangeError (交易所返回的错误)
# │   ├── AuthenticationError (认证失败)
# │   ├── PermissionDenied (权限不足)
# │   ├── AccountSuspended (账户暂停)
# │   ├── ArgumentsRequired (缺少参数)
# │   ├── BadRequest (请求格式错误)
# │   ├── BadSymbol (无效交易对)
# │   ├── MarginModeAlreadySet (保证金模式已设置)
# │   ├── MarketClosed (市场关闭)
# │   ├── InsufficientFunds (余额不足)
# │   ├── InvalidOrder (无效订单)
# │   │   ├── OrderNotFound (订单不存在)
# │   │   └── OrderNotCached (订单未缓存)
# │   ├── CancelPending (取消待处理)
# │   ├── OrderNotFillable (订单无法成交)
# │   ├── DuplicateOrderId (重复订单ID)
# │   ├── ContractUnavailable (合约不可用)
# │   ├── NotSupported (功能不支持)
# │   └── ExchangeNotAvailable (交易所不可用)
# │       ├── OnMaintenance (维护中)
# │       └── RequestTimeout (请求超时)
# │           └── NetworkError (网络错误)
# └── OperationFailed (操作失败)
#     ├── OperationRejected (操作被拒)
#     └── RateLimitExceeded (频率限制)
# ==================== END ====================


class Trader:
    """全面的订单管理器"""
    
    def __init__(self, exchange_cfg: dict):
        if not exchange_cfg:
            raise ValueError("Exchange configuration is required")
        if not exchange_cfg.get('apikey') or not exchange_cfg.get('secretkey'):
            raise ValueError("API key and secret key are required")
        
        self.exchange_cfg = exchange_cfg
        # 使用 type 字段获取 CCXT 交易所类型（如 hyperliquid），而非用户自定义的 name
        self.exchange_name = exchange_cfg.get('type', '').lower()
        self.exchange_display_name = exchange_cfg.get('name', self.exchange_name)
        
        logger.info(f"Initializing exchange: {self.exchange_display_name} (type: {self.exchange_name})")
        exchange_class = getattr(ccxtpro, self.exchange_name)
        
        # 构建 options，支持从数据库配置滑点
        options = {
            'defaultType': 'swap',
        }
        
        # 如果配置了滑点，则添加（用于 Hyperliquid 等需要滑点的交易所）
        if exchange_cfg.get('slippage'):
            options['slippage'] = float(exchange_cfg['slippage'])
            logger.info(f"💰 Slippage configured: {options['slippage']*100:.1f}%")
        
        self.exchange = exchange_class({
            'apiKey': exchange_cfg['apikey'],
            'walletAddress': exchange_cfg['apikey'],  # 一样的 apikey
            'secret': exchange_cfg['secretkey'],
            'privateKey': exchange_cfg['secretkey'],
            'testnet': exchange_cfg.get('testnet', True),
            'enableRateLimit': True,
            'options': options
        })
        
        self.markets = None
        self._capabilities = {}
        logger.info("CCXT Pro Exchange instance created!")
    
    async def async_init(self):
        """异步初始化 - 加载市场和检测能力"""
        logger.info("Loading markets asynchronously...")
        
        # 1. 检查交易所状态
        await self._check_exchange_status()
        
        # 2. 加载市场
        self.markets = await self.exchange.load_markets()
        logger.info(f"Loaded {len(self.markets)} markets")
        
        # 3. 检测能力
        self._detect_capabilities()
        return self
    
    async def _check_exchange_status(self):
        """
        检查交易所状态
        
        参考: https://docs.ccxt.com/README?id=exchangenotavailable
        
        使用 fetch_status() API 检查交易所是否正常运行
        """
        try:
            if hasattr(self.exchange, 'fetch_status'):
                status = await self.exchange.fetch_status()
                
                # CCXT 状态格式: {"status": "ok" | "maintenance" | "error", "updated": timestamp, "eta": timestamp, "url": string}
                exchange_status = status.get('status', 'unknown')
                
                if exchange_status == 'ok':
                    logger.info(f"✅ Exchange status: OK")
                elif exchange_status == 'maintenance':
                    eta = status.get('eta')
                    msg = status.get('msg', 'Scheduled maintenance')
                    logger.warning(f"⚠️ Exchange is under maintenance: {msg}")
                    if eta:
                        logger.warning(f"   Expected back at: {eta}")
                    # 不抛出异常，让调用者决定如何处理
                else:
                    logger.warning(f"⚠️ Exchange status: {exchange_status}")
            else:
                logger.debug("Exchange does not support fetch_status()")
                
        except ccxt.ExchangeNotAvailable as e:
            logger.error(f"❌ Exchange not available: {e}")
            raise
        except ccxt.NetworkError as e:
            logger.error(f"❌ Network error checking exchange status: {e}")
            raise
        except Exception as e:
            # 非关键错误，记录但不阻止初始化
            logger.warning(f"⚠️ Failed to check exchange status: {e}")
    
    def _detect_capabilities(self):
        """检测交易所支持的功能"""
        self._capabilities = {
            'ws_create_order': self.exchange.has.get('createOrderWs', False),
            'ws_edit_order': self.exchange.has.get('editOrderWs', False),
            'ws_cancel_order': self.exchange.has.get('cancelOrderWs', False),
            'stop_order': self.exchange.has.get('createStopOrder', False),
            'stop_limit_order': self.exchange.has.get('createStopLimitOrder', False),
            'trailing_stop': self.exchange.has.get('createTrailingAmountOrder', False),
            'set_leverage': self.exchange.has.get('setLeverage', False),
            'position_side': self.exchange_name in ['binance', 'bybit', 'okx'],
            # Hyperliquid 支持在主订单中附加 SL/TP（通过 stopLossPrice/takeProfitPrice）
            'attached_sl_tp': self.exchange_name in ['binance', 'bybit', 'okx', 'hyperliquid'],
        }
        logger.info(f"Exchange capabilities: {self._capabilities}")
    
    def get_trading_fee_rate(self, symbol: str, order_type: str = 'market') -> float:
        """
        获取交易手续费率
        
        Args:
            symbol: 交易对
            order_type: 订单类型（market或limit）
            
        Returns:
            费率（小数形式，如0.0005表示0.05%）
        """
        return FeeCalculator.get_trading_fee_rate(self.exchange, symbol, order_type)
    
    # ==================== 创建订单 ====================
    
    async def create_order(
        self,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        amount: float,
        price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        leverage: int = 1,
        reduce_only: bool = False,
        position_side: Optional[PositionSide] = None,
    ) -> OrderResult:
        """
        统一的下单接口
        
        Args:
            symbol: 交易对 (如 BTC/USDT:USDT)
            order_type: 订单类型 (market, limit, stop, etc.)
            side: 买卖方向 (buy, sell)
            amount: 数量
            price: 价格（限价单必填）
            stop_loss: 止损价（可选）
            take_profit: 止盈价（可选）
            leverage: 杠杆倍数
            reduce_only: 只减仓
            position_side: 持仓方向（双向模式时需要）
        """
        try:
            # 1. 设置杠杆
            await self._set_leverage(symbol, leverage)
            
            # 2. 构建参数
            params = self._build_order_params(
                symbol, side, stop_loss, take_profit, 
                reduce_only, position_side
            )
            
            # 🔧 记录预期手续费（用于验证）
            expected_fee_rate = self.get_trading_fee_rate(symbol, order_type)
            if price:
                expected_notional = amount * price
                expected_fee = FeeCalculator.calculate_fee(expected_notional, expected_fee_rate)
                logger.info(
                    f"💰 Expected fee: ${expected_fee:.4f} "
                    f"(rate: {expected_fee_rate*100:.4f}%, notional: ${expected_notional:.2f})"
                )
            
            # 3. 下单
            logger.debug(f"📤 Sending order: symbol={symbol}, type={order_type}, side={side}, amount={amount}, price={price}, params={params}")
            
            if self._capabilities.get('ws_create_order'):
                order = await self.exchange.create_order_ws(
                    symbol, order_type, side, amount, price, params
                )
            else:
                order = await self.exchange.create_order(
                    symbol, order_type, side, amount, price, params
                )
            
            logger.debug(f"📥 Order response: {order}")
            
            # 🔧 检查订单是否创建成功
            if order is None:
                logger.error(f"❌ Exchange returned None for order: {symbol} {side} {amount}")
                return OrderResult(success=False, error="Exchange returned None - check API credentials and params")
            
            # 🔧 验证实际手续费（注意：某些交易所如 Hyperliquid 返回 fee=None）
            if order and order.get('fee'):
                actual_fee = order['fee'].get('cost', 0)
                if price and expected_fee > 0:
                    fee_diff_pct = abs(actual_fee - expected_fee) / expected_fee * 100
                    if fee_diff_pct > 10:
                        logger.warning(
                            f"⚠️ Fee mismatch: expected ${expected_fee:.4f}, "
                            f"got ${actual_fee:.4f} (diff: {fee_diff_pct:.1f}%)"
                        )
                    else:
                        logger.debug(f"✅ Fee verified: ${actual_fee:.4f}")
            
            # 解析订单结果
            order_result = self._parse_order_result(order)
            
            # 详细日志：订单状态
            order_status = order.get('status', 'unknown')
            filled = order_result.filled or 0
            remaining = order_result.remaining or 0
            order_id = order_result.order_id
            
            logger.info(
                f"✅ Order created: {symbol} {side} {amount} @ {price or 'market'} | "
                f"ID: {order_id} | Status: {order_status} | "
                f"Filled: {filled} | Remaining: {remaining}"
            )
            
            # 警告：如果订单状态不是 'closed' 或 'filled'，说明可能还没完全成交
            if order_status not in ['closed', 'filled']:
                logger.warning(
                    f"⚠️ {symbol}: Order status is '{order_status}', not 'closed'. "
                    f"This might indicate the order is still pending. "
                    f"Filled: {filled}, Remaining: {remaining}"
                )
            
            return order_result
        
        # ==================== CCXT 异常处理 ====================
        # 按照 CCXT 文档的异常层次结构处理
        # 参考: https://docs.ccxt.com/README?id=error-handling
            
        except ccxt.InsufficientFunds as e:
            # 余额不足 - 可恢复，需要减少仓位或等待资金
            logger.error(f"❌ Insufficient funds: {symbol} - {e}")
            return OrderResult(success=False, error=f"Insufficient funds: {e}")
        
        except ccxt.InvalidOrder as e:
            # 无效订单（价格/数量不符合交易所规则）
            logger.error(f"❌ Invalid order: {symbol} - {e}")
            return OrderResult(success=False, error=f"Invalid order: {e}")
        
        except ccxt.AuthenticationError as e:
            # 认证失败 - 需要检查 API Key
            logger.error(f"🔐 Authentication failed: {e}")
            return OrderResult(success=False, error=f"Authentication failed: {e}")
        
        except ccxt.ExchangeNotAvailable as e:
            # 交易所不可用（维护或网络问题）- CCXT 会自动重试
            logger.error(f"🔌 Exchange not available: {e}")
            return OrderResult(success=False, error=f"Exchange not available: {e}")
        
        except ccxt.RateLimitExceeded as e:
            # 频率限制 - CCXT 的 enableRateLimit 会自动处理
            logger.warning(f"⏳ Rate limit exceeded: {e}")
            return OrderResult(success=False, error=f"Rate limit exceeded: {e}")
        
        except ccxt.NetworkError as e:
            # 网络错误 - 可能需要重试
            logger.error(f"🌐 Network error: {e}")
            return OrderResult(success=False, error=f"Network error: {e}")
        
        except ccxt.ExchangeError as e:
            # 其他交易所错误
            logger.error(f"❌ Exchange error: {e}")
            return OrderResult(success=False, error=f"Exchange error: {e}")
            
        except Exception as e:
            # 未知错误
            logger.error(f"❌ Create order failed (unknown): {e}")
            return OrderResult(success=False, error=str(e))
    
    def _build_order_params(
        self,
        symbol: str,
        side: OrderSide,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        reduce_only: bool,
        position_side: Optional[PositionSide],
    ) -> Dict[str, Any]:
        """构建交易所特定参数"""
        params = {}
        
        # Reduce only
        if reduce_only:
            params['reduceOnly'] = True
        
        # Position side (双向模式)
        if position_side and self._capabilities.get('position_side'):
            params['positionSide'] = position_side.upper()
        
        # 止损止盈（仅支持附加的交易所）
        if self._capabilities.get('attached_sl_tp') and (stop_loss or take_profit):
            params.update(self._build_sl_tp_params(symbol, side, stop_loss, take_profit))
        
        # Hyperliquid 特殊处理
        if self.exchange_name == 'hyperliquid':
            params['user'] = self.exchange_cfg.get('apikey')
        
        return params
    
    def _build_sl_tp_params(
        self,
        symbol: str,
        side: OrderSide,
        stop_loss: Optional[float],
        take_profit: Optional[float],
    ) -> Dict[str, Any]:
        """构建止损止盈参数（交易所差异最大的部分）"""
        params = {}
        
        if self.exchange_name == 'binance':
            if stop_loss:
                params['stopLoss'] = {'stopPrice': stop_loss, 'type': 'STOP_MARKET'}
            if take_profit:
                params['takeProfit'] = {'stopPrice': take_profit, 'type': 'TAKE_PROFIT_MARKET'}
                
        elif self.exchange_name == 'bybit':
            if stop_loss:
                params['stopLoss'] = str(stop_loss)
            if take_profit:
                params['takeProfit'] = str(take_profit)
                
        elif self.exchange_name == 'okx':
            algo_orders = []
            if stop_loss:
                algo_orders.append({'slTriggerPx': str(stop_loss), 'slOrdPx': '-1'})
            if take_profit:
                algo_orders.append({'tpTriggerPx': str(take_profit), 'tpOrdPx': '-1'})
            if algo_orders:
                params['attachAlgoOrds'] = algo_orders
                
        elif self.exchange_name == 'hyperliquid':
            # Hyperliquid: 使用 stopLoss/takeProfit 字典格式
            # CCXT 会在 create_orders_request 中将主订单和 SL/TP 打包成 normalTpsl 分组请求
            # 参考: ccxt/hyperliquid.py create_orders_request() 第 1941-1973 行
            if stop_loss:
                params['stopLoss'] = {'triggerPrice': stop_loss}
            if take_profit:
                params['takeProfit'] = {'triggerPrice': take_profit}
        else:
            # 通用方案
            if stop_loss:
                params['stopLossPrice'] = stop_loss
            if take_profit:
                params['takeProfitPrice'] = take_profit
        
        return params
    
    async def _set_leverage(self, symbol: str, leverage: int):
        """设置杠杆"""
        if not self._capabilities.get('set_leverage'):
            return
        try:
            await self.exchange.set_leverage(leverage, symbol)
            logger.info(f"Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            logger.warning(f"Failed to set leverage: {e}")
    
    # ==================== 条件单（止损/止盈） ====================
    
    async def create_stop_loss_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        stop_price: float,
        reduce_only: bool = True,
    ) -> OrderResult:
        """
        创建止损单
        
        使用 'stop' 订单类型，CCXT 会自动处理触发逻辑
        """
        try:
            params = {'reduceOnly': reduce_only}
            
            # Hyperliquid 特殊处理
            if self.exchange_name == 'hyperliquid':
                params['user'] = self.exchange_cfg.get('apikey')
                params['triggerPx'] = stop_price
                params['orderType'] = 'stop_market'
            
            order = await self.exchange.create_order(
                symbol, 'stop', side, amount, stop_price, params
            )
            
            logger.info(f"✅ Stop loss created: {symbol} @ {stop_price}")
            return self._parse_order_result(order)
        
        except ccxt.NotSupported as e:
            logger.warning(f"⚠️ Stop loss not supported: {e}")
            return OrderResult(success=False, error=f"Stop loss not supported by exchange: {e}")
        except ccxt.InvalidOrder as e:
            logger.error(f"❌ Invalid stop loss order: {e}")
            return OrderResult(success=False, error=f"Invalid stop loss: {e}")
        except ccxt.ExchangeError as e:
            logger.error(f"❌ Create stop loss failed: {e}")
            return OrderResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"❌ Create stop loss failed (unknown): {e}")
            return OrderResult(success=False, error=str(e))
    
    async def create_take_profit_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        trigger_price: float,
        reduce_only: bool = True,
    ) -> OrderResult:
        """
        创建止盈单
        
        使用 'take_profit' 订单类型，CCXT 会自动处理触发逻辑
        """
        try:
            params = {'reduceOnly': reduce_only}
            
            # Hyperliquid 特殊处理
            if self.exchange_name == 'hyperliquid':
                params['user'] = self.exchange_cfg.get('apikey')
                params['triggerPx'] = trigger_price
                params['orderType'] = 'take_profit_market'
            
            order = await self.exchange.create_order(
                symbol, 'take_profit', side, amount, trigger_price, params
            )
            
            logger.info(f"✅ Take profit created: {symbol} @ {trigger_price}")
            return self._parse_order_result(order)
        
        except ccxt.NotSupported as e:
            logger.warning(f"⚠️ Take profit not supported: {e}")
            return OrderResult(success=False, error=f"Take profit not supported by exchange: {e}")
        except ccxt.InvalidOrder as e:
            logger.error(f"❌ Invalid take profit order: {e}")
            return OrderResult(success=False, error=f"Invalid take profit: {e}")
        except ccxt.ExchangeError as e:
            logger.error(f"❌ Create take profit failed: {e}")
            return OrderResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"❌ Create take profit failed (unknown): {e}")
            return OrderResult(success=False, error=str(e))
    
    # ==================== 修改订单 ====================
    
    async def edit_order(
        self,
        order_id: str,
        symbol: str,
        order_type: OrderType,
        side: OrderSide,
        amount: Optional[float] = None,
        price: Optional[float] = None,
    ) -> OrderResult:
        """修改订单"""
        try:
            if self._capabilities.get('ws_edit_order'):
                order = await self.exchange.edit_order_ws(
                    order_id, symbol, order_type, side, amount, price
                )
            else:
                order = await self.exchange.edit_order(
                    order_id, symbol, order_type, side, amount, price
                )
            logger.info(f"✅ Order edited: {order_id}")
            return self._parse_order_result(order)
        
        except ccxt.OrderNotFound as e:
            logger.warning(f"⚠️ Order not found: {order_id}")
            return OrderResult(success=False, error=f"Order not found: {e}")
        except ccxt.NotSupported as e:
            logger.warning(f"⚠️ Edit order not supported by exchange")
            return OrderResult(success=False, error=f"Edit not supported: {e}")
        except ccxt.ExchangeError as e:
            logger.error(f"❌ Edit order failed: {e}")
            return OrderResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"❌ Edit order failed (unknown): {e}")
            return OrderResult(success=False, error=str(e))
    
    # ==================== 取消订单 ====================
    
    async def cancel_order(self, order_id: str, symbol: str) -> OrderResult:
        """取消单个订单"""
        try:
            if self._capabilities.get('ws_cancel_order'):
                result = await self.exchange.cancel_order_ws(order_id, symbol)
            else:
                result = await self.exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Order cancelled: {order_id}")
            return self._parse_order_result(result)
        
        except ccxt.OrderNotFound as e:
            # 订单可能已成交或已取消
            logger.warning(f"⚠️ Order not found (may be filled/cancelled): {order_id}")
            return OrderResult(success=False, error=f"Order not found: {e}")
        except ccxt.CancelPending as e:
            # 取消已在处理中
            logger.info(f"ℹ️ Cancel already pending: {order_id}")
            return OrderResult(success=True, error=f"Cancel pending: {e}")
        except ccxt.ExchangeError as e:
            logger.error(f"❌ Cancel order failed: {e}")
            return OrderResult(success=False, error=str(e))
        except Exception as e:
            logger.error(f"❌ Cancel order failed (unknown): {e}")
            return OrderResult(success=False, error=str(e))
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[OrderResult]:
        """取消所有订单"""
        try:
            results = await self.exchange.cancel_all_orders(symbol)
            logger.info(f"✅ Cancelled {len(results)} orders")
            return [self._parse_order_result(r) for r in results]
        except Exception as e:
            logger.error(f"❌ Cancel all orders failed: {e}")
            return []
    
    # ==================== 查询订单 ====================
    
    async def fetch_order(self, order_id: str, symbol: str) -> Optional[OrderResult]:
        """查询单个订单"""
        try:
            order = await self.exchange.fetch_order(order_id, symbol)
            return self._parse_order_result(order)
        except Exception as e:
            logger.error(f"❌ Fetch order failed: {e}")
            return None
    
    async def fetch_open_orders(self, symbol: Optional[str] = None) -> List[OrderResult]:
        """查询未成交订单"""
        try:
            orders = await self.exchange.fetch_open_orders(symbol)
            return [self._parse_order_result(o) for o in orders]
        except Exception as e:
            logger.error(f"❌ Fetch open orders failed: {e}")
            return []
    
    # ==================== 一键开仓（带止损止盈） ====================
    
    async def open_position(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        leverage: int = 1,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: OrderType = "market",
        price: Optional[float] = None,
    ) -> OpenPositionResult:
        """
        一键开仓：主订单 + 止损 + 止盈
        
        Returns:
            OpenPositionResult: 包含 main, stop_loss, take_profit 三个订单结果
        """
        result = OpenPositionResult()
        
        # 1. 主订单
        main_result = await self.create_order(
            symbol=symbol,
            order_type=order_type,
            side=side,
            amount=amount,
            price=price,
            leverage=leverage,
            stop_loss=stop_loss if self._capabilities.get('attached_sl_tp') else None,
            take_profit=take_profit if self._capabilities.get('attached_sl_tp') else None,
        )
        result.main = main_result
        
        if not main_result.success:
            return result
        
        # 2. 如果交易所不支持附加止损止盈，单独下条件单
        if not self._capabilities.get('attached_sl_tp'):
            close_side: OrderSide = "sell" if side == "buy" else "buy"
            
            if stop_loss:
                result.stop_loss = await self.create_stop_loss_order(
                    symbol, close_side, amount, stop_loss
                )
            
            if take_profit:
                result.take_profit = await self.create_take_profit_order(
                    symbol, close_side, amount, take_profit
                )
        
        return result
    
    async def close_position(
        self, 
        symbol: str, 
        amount: Optional[float] = None
    ) -> OrderResult:
        """平仓
        
        注意：Hyperliquid 市价单需要价格参数来计算滑点保护价格
        """
        logger.info(f"📤 close_position called: symbol={symbol}, amount={amount}")
        
        try:
            position = await self.get_position(symbol)
            
            if not position:
                logger.warning(f"⚠️ {symbol}: No position found in exchange to close")
                return OrderResult(success=False, error="No position found")
            
            # 日志：找到的持仓信息
            logger.info(f"📦 {symbol}: Found position - side={position.side}, amount={position.amount}, avg_price={position.average}")
            
            close_amount = amount or position.amount
            close_side: OrderSide = "sell" if position.side == 'buy' else "buy"
            
            logger.info(f"📊 {symbol}: Preparing close order - side={close_side}, amount={close_amount}")
            
            # Hyperliquid 市价单需要价格来计算滑点保护价格
            current_price = None
            if self.exchange_name == 'hyperliquid':
                ticker = await self.exchange.fetch_ticker(symbol)
                current_price = ticker.get('last') or ticker.get('close') or ticker.get('bid') or ticker.get('ask')
                logger.info(f"💰 {symbol}: Using price {current_price} for slippage calculation")
            
            result = await self.create_order(
                symbol=symbol,
                order_type="market",
                side=close_side,
                amount=close_amount,
                price=current_price,  # Hyperliquid 需要此参数计算滑点
                reduce_only=True,
            )
            
            if result.success:
                logger.info(f"✅ {symbol}: Close order executed - order_id={result.order_id}, filled={result.filled}, avg={result.average}")
            else:
                logger.error(f"❌ {symbol}: Close order failed - {result.error}")
            
            return result
            
        except Exception as e:
            logger.error(f"🚨 {symbol}: Exception in close_position - {type(e).__name__}: {e}")
            return OrderResult(success=False, error=str(e))
    
    # ==================== 监听订单 ====================
    
    async def watch_orders(self, symbol: Optional[str] = None):
        """监听订单状态变化"""
        while True:
            orders = await self.exchange.watch_orders(symbol)
            for order in orders:
                yield self._parse_order_result(order)
    
    # ==================== 持仓管理 ====================
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """获取单个持仓"""
        logger.debug(f"📡 get_position: querying {symbol}")
        positions = await self.get_positions([symbol])
        
        if positions:
            pos = positions[0]
            logger.info(f"📦 get_position: {symbol} found - side={pos.side}, amount={pos.amount}")
            return pos
        else:
            logger.info(f"📦 get_position: {symbol} not found in active positions")
            return None
    
    async def get_positions(self, symbols: List[str] = None) -> List[Position]:
        """获取当前持仓"""
        try:
            logger.info("Fetching positions...")
            
            params = {}
            if self.exchange_name == 'hyperliquid':
                params['user'] = self.exchange_cfg.get('apikey')
            
            all_positions = await self.exchange.fetch_positions(symbols, params)
            logger.info(f"Received {len(all_positions)} position records")
            
            # 过滤掉空持仓
            active_positions = [
                p for p in all_positions 
                if p.get('contracts') and float(p.get('contracts', 0)) != 0
            ]
            
            # 日志：显示活跃持仓的 symbol
            active_symbols = [p.get('symbol', 'unknown') for p in active_positions]
            logger.info(f"Found {len(active_positions)} active positions: {active_symbols}")
            
            positions = []
            for pos in active_positions:
                try:
                    contracts = float(pos.get('contracts', 0))
                    
                    # 优先使用 CCXT 返回的 side 字段（如 Hyperliquid 等交易所）
                    # 回退到 contracts 符号判断（如某些交易所用负数表示空头）
                    raw_side = pos.get('side', '').lower()
                    if raw_side == 'long':
                        side = 'buy'
                    elif raw_side == 'short':
                        side = 'sell'
                    else:
                        # 回退：contracts > 0 为多头，< 0 为空头
                        side = 'buy' if contracts > 0 else 'sell'
                    
                    timestamp = pos.get('timestamp', 0)
                    dt = datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now()
                    
                    # 解析杠杆信息（CCXT 统一格式）
                    leverage = 1
                    leverage_info = pos.get('leverage')
                    if leverage_info:
                        # 可能是数字或字典
                        if isinstance(leverage_info, dict):
                            leverage = int(leverage_info.get('value', 1))
                        else:
                            leverage = int(leverage_info)
                    
                    position = Position(
                        id=str(pos.get('id', f"{pos['symbol']}_{timestamp}")),
                        symbol=pos['symbol'],
                        side=side,
                        type='market',
                        status='open',
                        datetime=dt,
                        last_trade_timestamp=None,
                        price=float(pos.get('entryPrice', 0)),
                        average=float(pos.get('entryPrice', 0)),
                        amount=abs(contracts),
                        leverage=leverage,
                        trigger_price=None,
                        take_profit_price=None,
                        stop_loss_price=None,
                    )
                    positions.append(position)
                    logger.debug(f"📦 Parsed position: {pos['symbol']} amount={abs(contracts):.6f} leverage={leverage}x")
                    
                except Exception as e:
                    logger.error(f"Failed to parse position {pos.get('symbol', 'unknown')}: {e}")
                    continue
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}", exc_info=True)
            return []
    
    # ==================== 账户信息 ====================
    
    async def get_account_info(self) -> Account:
        """获取账户信息"""
        params = {}
        if self.exchange_name == 'hyperliquid':
            params['user'] = self.exchange_cfg.get('apikey')
        
        _original_balance = await self.exchange.fetch_balance(params)
        logger.info(f"Original balance: {_original_balance}")
        
        timestamp_ms = _original_balance.get('timestamp')
        account = Account(
            timestamp=timestamp_ms,
            free=_original_balance.get('free', {}),
            used=_original_balance.get('used', {}),
            total=_original_balance.get('total', {}),
            debt=_original_balance.get('debt', {}),
            info=_original_balance.get('info', None)
        )
        return account
    
    # ==================== OHLCV 数据 ====================
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100):
        """获取 K 线数据"""
        logger.info(f"Fetching OHLCV for {symbol} {timeframe} {limit}")
        return await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    async def watch_ohlcv(self, symbol: str, timeframe: str):
        """监听 K 线流"""
        while True:
            ohlcv = await self.exchange.watch_ohlcv(symbol, timeframe)
            yield ohlcv
    
    async def watch_tickers(self, symbols: List[str]):
        """监听多个 ticker"""
        return await self.exchange.watch_tickers(symbols)
    
    # ==================== 辅助方法 ====================
    
    def _parse_order_result(self, order: Dict[str, Any]) -> OrderResult:
        """解析订单结果为统一格式"""
        return OrderResult(
            success=True,
            order_id=order.get('id'),
            symbol=order.get('symbol'),
            status=order.get('status'),
            filled=float(order.get('filled') or 0),      # 处理 None 值
            remaining=float(order.get('remaining') or 0),  # 处理 None 值
            average=order.get('average'),
            fee=order.get('fee', {}).get('cost') if order.get('fee') else None,
            raw=order,
        )
    
    async def close(self):
        """关闭连接"""
        await self.exchange.close()
