# packages/langtrader_core/graph/nodes/coins_pick.py
"""
选币节点 - 使用评分系统选择交易币种
"""
from langtrader_core.utils import get_logger
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import State
from langtrader_core.services.coin import Coin

logger = get_logger("coins_pick")


class CoinsPick(NodePlugin):
    """
    The node that picks the coins to trade.
    使用评分系统选择最佳交易币种
    """
    
    metadata = NodeMetadata(
        name="coins_pick",
        display_name="Coin Selection",
        version="1.0.0",
        author="LangTrader official",
        description="The node that picks the coins to trade. using a score system to pick the coins.",
        category="Basic",
        tags=["coins_pick", "official"],
        inputs=[],
        outputs=["symbols"],
        requires=[],
        requires_trader=True,
        suggested_order=1,
        auto_register=True,
        config_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "The number of coins to pick",
                    "default": 20
                },
                "use_open_interest": {
                    "type": "boolean",
                    "description": "Whether to use open interest to pick the coins",
                    "default": True
                }
            }
        },
        default_config={
            "limit": 20,
            "use_open_interest": True
        }
    )
    
    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        
        # 从 context 获取共享实例
        trader = context.trader if context else None
        stream_manager = context.stream_manager if context else None
        cache = context.cache if context else None          # ← 从 context 获取
        rate_limiter = context.rate_limiter if context else None  # ← 从 context 获取
        
        # 使用注入的共享实例创建 Coin 服务
        self.coin = Coin(
            trader=trader,
            cache=cache,
            rate_limiter=rate_limiter
        )
        
        self.stream_manager = stream_manager
        self.use_open_interest = config.get('use_open_interest', True) if config else True

    async def run(self, state: State):
        """
        选币 + 自动更新 WebSocket 订阅
        """
        # 🔧 如果已经有预设的 symbols（回测模式），直接使用
        if state.symbols and len(state.symbols) > 0:
            logger.info(f"📦 Using preset symbols (backtest mode): {len(state.symbols)} coins")
            logger.info(f"   Symbols: {state.symbols}")
            return state
        
        # 检查缓存的选币结果
        cached_symbols = self.coin.cache.get('coin_selection')

        if cached_symbols:
            logger.info(f"📦 Using cached symbols: {len(cached_symbols)} coins")
            state.symbols = cached_symbols
            
            # ⚠️ 即使使用缓存，也要确保订阅是最新的
            if self.stream_manager:
                await self.stream_manager.sync_subscriptions(cached_symbols, ['3m'])
            
            return state

        # 执行完整的选币流程
        logger.info("🔍 Cache miss, starting coin selection...")

        top_20_oi_coins = []
        if self.use_open_interest:
            top_20_oi_coins = await self.coin.select_io_top(limit=20)
        
        top_20_raw_coins = self.coin.select_top(limit=20)
        logger.info(f"  Raw coins (volume): {len(top_20_raw_coins)}")
        logger.info(f"  Open Interest coins: {len(top_20_oi_coins)}")
        
        # 合并去重
        combined_coins = self.coin.combine_unique_coins(top_20_oi_coins, top_20_raw_coins, limit=5)
        logger.info(f"  Combined unique: {len(combined_coins)} coins")
        
        # 评分排序
        scored_coins = await self.coin.score_coins(combined_coins)
        logger.info(f"✅ Final selection: {len(scored_coins)} coins")
        
        # 缓存结果
        self.coin.cache.set('coin_selection', scored_coins)
        state.symbols = scored_coins
        
        # 🔥 关键：自动同步 WebSocket 订阅
        if self.stream_manager:
            logger.info("📡 Syncing WebSocket subscriptions...")
            await self.stream_manager.sync_subscriptions(scored_coins, ['3m'])
        
        return state
