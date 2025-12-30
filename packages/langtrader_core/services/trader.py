"""
Trader - 全面的订单管理（基于 CCXT Pro）

支持功能：
- 创建订单（市价/限价/止损/止盈）
- 修改订单
- 取消订单
- 一键开仓（主订单 + 止损 + 止盈）
- 平仓
- 查询订单/持仓
"""
import ccxt.pro as ccxtpro
from datetime import datetime
from typing import Optional, Dict, List, Any

from langtrader_core.graph.state import (
    Account, Position, OrderResult, OpenPositionResult,
    OrderType, OrderSide, PositionSide
)
from langtrader_core.utils import get_logger

logger = get_logger("trader")


class Trader:
    """全面的订单管理器"""
    
    def __init__(self, exchange_cfg: dict):
        if not exchange_cfg:
            raise ValueError("Exchange configuration is required")
        if not exchange_cfg.get('apikey') or not exchange_cfg.get('secretkey'):
            raise ValueError("API key and secret key are required")
        
        self.exchange_cfg = exchange_cfg
        self.exchange_name = exchange_cfg.get('name', '').lower()
        
        logger.info(f"Initializing exchange: {self.exchange_name}")
        exchange_class = getattr(ccxtpro, self.exchange_name)
        
        self.exchange = exchange_class({
            'apiKey': exchange_cfg['apikey'],
            'secret': exchange_cfg['secretkey'],
            'privateKey':exchange_cfg['secretkey'],
            'testnet': exchange_cfg.get('testnet', True),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
            }
        })
        
        self.markets = None
        self._capabilities = {}
        logger.info("CCXT Pro Exchange instance created!")
    
    async def async_init(self):
        """异步初始化 - 加载市场和检测能力"""
        logger.info("Loading markets asynchronously...")
        self.markets = await self.exchange.load_markets()
        logger.info(f"Loaded {len(self.markets)} markets")
        
        self._detect_capabilities()
        return self
    
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
            'attached_sl_tp': self.exchange_name in ['binance', 'bybit', 'okx'],
        }
        logger.info(f"Exchange capabilities: {self._capabilities}")
    
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
            
            # 3. 下单
            if self._capabilities.get('ws_create_order'):
                order = await self.exchange.create_order_ws(
                    symbol, order_type, side, amount, price, params
                )
            else:
                order = await self.exchange.create_order(
                    symbol, order_type, side, amount, price, params
                )
            
            logger.info(f"✅ Order created: {symbol} {side} {amount} @ {price or 'market'}")
            return self._parse_order_result(order)
            
        except Exception as e:
            logger.error(f"❌ Create order failed: {e}")
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
        """创建止损单"""
        try:
            params = {'reduceOnly': reduce_only}
            
            if self.exchange_name == 'hyperliquid':
                params['user'] = self.exchange_cfg.get('apikey')
                params['triggerPx'] = stop_price
                params['orderType'] = 'stop_market'
            
            order = await self.exchange.create_order(
                symbol, 'stop', side, amount, stop_price, params
            )
            logger.info(f"✅ Stop loss created: {symbol} @ {stop_price}")
            return self._parse_order_result(order)
            
        except Exception as e:
            logger.error(f"❌ Create stop loss failed: {e}")
            return OrderResult(success=False, error=str(e))
    
    async def create_take_profit_order(
        self,
        symbol: str,
        side: OrderSide,
        amount: float,
        trigger_price: float,
        reduce_only: bool = True,
    ) -> OrderResult:
        """创建止盈单"""
        try:
            params = {'reduceOnly': reduce_only}
            
            if self.exchange_name == 'hyperliquid':
                params['user'] = self.exchange_cfg.get('apikey')
            
            order = await self.exchange.create_order(
                symbol, 'take_profit', side, amount, trigger_price, params
            )
            logger.info(f"✅ Take profit created: {symbol} @ {trigger_price}")
            return self._parse_order_result(order)
            
        except Exception as e:
            logger.error(f"❌ Create take profit failed: {e}")
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
            
        except Exception as e:
            logger.error(f"❌ Edit order failed: {e}")
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
            
        except Exception as e:
            logger.error(f"❌ Cancel order failed: {e}")
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
        """平仓"""
        try:
            position = await self.get_position(symbol)
            if not position:
                return OrderResult(success=False, error="No position found")
            
            close_amount = amount or position.amount
            close_side: OrderSide = "sell" if position.side == 'buy' else "buy"
            
            return await self.create_order(
                symbol=symbol,
                order_type="market",
                side=close_side,
                amount=close_amount,
                reduce_only=True,
            )
        except Exception as e:
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
        positions = await self.get_positions([symbol])
        return positions[0] if positions else None
    
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
            
            logger.info(f"Found {len(active_positions)} active positions")
            
            positions = []
            for pos in active_positions:
                try:
                    contracts = float(pos.get('contracts', 0))
                    side = 'buy' if contracts > 0 else 'sell'
                    
                    timestamp = pos.get('timestamp', 0)
                    dt = datetime.fromtimestamp(timestamp / 1000) if timestamp else datetime.now()
                    
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
                        trigger_price=None,
                        take_profit_price=None,
                        stop_loss_price=None,
                    )
                    positions.append(position)
                    
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
            filled=float(order.get('filled', 0)),
            remaining=float(order.get('remaining', 0)),
            average=order.get('average'),
            fee=order.get('fee', {}).get('cost') if order.get('fee') else None,
            raw=order,
        )
    
    async def close(self):
        """关闭连接"""
        await self.exchange.close()
