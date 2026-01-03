# packages/langtrader_core/services/fee_calculator.py
"""
统一的手续费计算器
支持从CCXT markets获取真实费率
"""
from typing import Optional, Dict, Any
from langtrader_core.utils import get_logger

logger = get_logger("fee_calculator")


class FeeCalculator:
    """统一的手续费计算器（支持回测和实盘）"""
    
    @staticmethod
    def get_trading_fee_rate(
        exchange: Any, 
        symbol: str, 
        order_type: str = 'market'
    ) -> float:
        """
        从exchange.markets获取交易手续费率
        
        Args:
            exchange: CCXT exchange实例（或MockTrader）
            symbol: 交易对（如 BTC/USDC:USDC）
            order_type: 订单类型（market或limit）
            
        Returns:
            费率（小数，如0.0005表示0.05%）
        """
        # 1. 优先从markets获取（最准确）
        if hasattr(exchange, 'markets') and exchange.markets:
            market = exchange.markets.get(symbol)
            if market:
                if order_type == 'market':
                    fee_rate = market.get('taker', 0.0007)
                else:
                    fee_rate = market.get('maker', 0.0002)
                
                logger.debug(
                    f"💰 {symbol} {order_type} fee from markets: "
                    f"{fee_rate*100:.4f}%"
                )
                return fee_rate
        
        # 2. 从exchange.fees获取默认费率
        if hasattr(exchange, 'fees') and exchange.fees:
            trading_fees = exchange.fees.get('trading', {})
            if trading_fees:
                if order_type == 'market':
                    fee_rate = trading_fees.get('taker', 0.0007)
                else:
                    fee_rate = trading_fees.get('maker', 0.0002)
                
                logger.debug(
                    f"💰 {symbol} {order_type} fee from exchange.fees: "
                    f"{fee_rate*100:.4f}%"
                )
                return fee_rate
        
        # 3. 使用保守估计
        logger.warning(
            f"⚠️ No fee info for {symbol}, using default 0.07% (taker)"
        )
        return 0.001 if order_type == 'market' else 0.0005
    
    @staticmethod
    def calculate_fee(
        notional_value: float,
        fee_rate: float
    ) -> float:
        """
        计算手续费
        
        Args:
            notional_value: 名义价值（币数量 × 价格 = USD金额）
            fee_rate: 费率（小数形式）
            
        Returns:
            手续费（USD）
        """
        fee = notional_value * fee_rate
        logger.debug(f"💰 Fee calc: ${notional_value:.2f} × {fee_rate*100:.4f}% = ${fee:.4f}")
        return fee
    
    @staticmethod
    def get_exchange_specific_rates(exchange_name: str) -> Dict[str, float]:
        """
        获取特定交易所的标准费率（作为fallback）
        
        根据公开文档的标准费率：
        - Hyperliquid: maker=0%, taker=0.035%
        - Binance: maker=0.02%, taker=0.04%
        - OKX: maker=0.08%, taker=0.1%
        - Bybit: maker=0.01%, taker=0.06%
        """
        EXCHANGE_FEES = {
            'hyperliquid': {'maker': 0.0, 'taker': 0.00035},
            'binance': {'maker': 0.0002, 'taker': 0.0004},
            'okx': {'maker': 0.0008, 'taker': 0.001},
            'bybit': {'maker': 0.0001, 'taker': 0.0006},
            'default': {'maker': 0.0005, 'taker': 0.001}
        }
        
        return EXCHANGE_FEES.get(
            exchange_name.lower(), 
            EXCHANGE_FEES['default']
        )
    
    @staticmethod
    def convert_usd_to_coin_amount(
        usd_amount: float,
        price: float
    ) -> float:
        """
        将USD金额转换为币数量
        
        Args:
            usd_amount: USD金额
            price: 币价格
            
        Returns:
            币数量
        """
        if price <= 0:
            raise ValueError(f"Invalid price: {price}")
        
        coin_amount = usd_amount / price
        logger.debug(f"💰 Convert: ${usd_amount:.2f} @ ${price:.2f} = {coin_amount:.8f} coins")
        return coin_amount

