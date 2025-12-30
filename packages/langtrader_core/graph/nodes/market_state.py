# packages/langtrader_core/graph/nodes/market_state.py
"""
市场状态节点 - 获取 K 线数据并计算技术指标
"""
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import State
from langtrader_core.services.market import Market
from langtrader_core.utils import get_logger

logger = get_logger("market_state")


class MarketState(NodePlugin):
    """
    市场状态节点
    - 获取 3m 和 4h K 线数据
    - 计算技术指标（EMA, MACD, RSI 等）
    """
    
    metadata = NodeMetadata(
        name="market_state",
        display_name="Market State",
        version="1.0.0",
        author="LangTrader official",
        description="The node that gets the market state.",
        category="Basic",
        tags=["market_state", "official"],
        insert_after="coins_pick",
        suggested_order=2,
        auto_register=True 
    )
    
    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        
        # 从 context 获取共享实例
        trader = context.trader if context else None
        stream_manager = context.stream_manager if context else None
        cache = context.cache if context else None          # ← 从 context 获取
        rate_limiter = context.rate_limiter if context else None  # ← 从 context 获取
        
        # 使用注入的共享实例创建 Market 服务
        self.market = Market(
            trader=trader,
            stream_manager=stream_manager,
            cache=cache,
            rate_limiter=rate_limiter
        )

    async def run(self, state: State):
        """
        获取市场数据并计算指标
        """
        try:
            state.market_data = await self.market.run(state)
            
            # 统计有指标的币种数量
            symbols_with_indicators = sum(
                1 for data in state.market_data.values() 
                if data.get('indicators') and len(data.get('indicators', {})) > 0
            )
            
            logger.info(f"✅ Indicators calculated: {symbols_with_indicators}/{len(state.market_data)} symbols")
            
            # 显示前几个币种的指标数量
            for idx, (symbol, data) in enumerate(list(state.market_data.items())[:3]):
                indicator_count = len(data.get('indicators', {}))
                logger.debug(f"   {symbol}: {indicator_count} indicators")
            
            # 显示当前持仓
            for item in state.positions:
                logger.info(f"current hold positions: {item}")
                
        except Exception as e:
            logger.error(f"Error getting market state: {e}")
            return state
        finally:
            logger.info("Market state node finished")
        
        return state
