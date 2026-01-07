# packages/langtrader_core/graph/nodes/market_state.py
"""
市场状态节点 - 获取 K 线数据并计算技术指标
"""
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import State
from langtrader_core.services.market import Market
from langtrader_core.utils import get_logger

import ccxt

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
        bot_config = context.bot_config if context else None  # ← 从 context 获取 BotConfig
        
        # 使用注入的共享实例创建 Market 服务
        self.market = Market(
            trader=trader,
            stream_manager=stream_manager,
            cache=cache,
            rate_limiter=rate_limiter,
            bot_config=bot_config  # 新增：传递 BotConfig
        )

    async def run(self, state: State):
        """
        获取市场数据并计算指标
        
        异常处理策略：
        - NetworkError: 可重试错误，记录警告
        - ExchangeNotAvailable: 交易所不可用，跳过本轮
        - ExchangeError: 交易所 API 错误，记录并跳过
        - 其他: 未知错误，记录并继续
        """
        try:
            state.market_data = await self.market.run(state)
            
            # 统计有指标的币种数量
            symbols_with_indicators = sum(
                1 for data in state.market_data.values() 
                if data.get('indicators') and len(data.get('indicators', {})) > 0
            )
            
            logger.info(f"Indicators calculated: {symbols_with_indicators}/{len(state.market_data)} symbols")
            
            # 显示前几个币种的指标数量
            for idx, (symbol, data) in enumerate(list(state.market_data.items())[:3]):
                indicator_count = len(data.get('indicators', {}))
                logger.debug(f"   {symbol}: {indicator_count} indicators")
            
            # ====== 关键修复：为已持仓的币种补充实时价格 ======
            # 如果持仓币种不在 coins_pick 选出的列表中，需要单独获取其实时价格
            # 否则止盈/止损策略无法正确计算 PnL
            await self._ensure_position_prices(state)
            
            # 显示当前持仓
            for item in state.positions:
                logger.info(f"Current hold position: {item}")
                
        except ccxt.NetworkError as e:
            # 网络错误（可重试）
            logger.warning(f"Network error (retryable): {e}")
        except ccxt.ExchangeNotAvailable as e:
            # 交易所不可用
            logger.error(f"Exchange not available: {e}")
        except ccxt.ExchangeError as e:
            # 交易所 API 错误
            logger.error(f"Exchange error: {e}")
        except Exception as e:
            # 未知错误
            logger.exception(f"Unexpected error in market state: {e}")
        finally:
            logger.info("Market state node finished")
        
        return state
    
    async def _ensure_position_prices(self, state: State):
        """
        确保已持仓的币种有实时价格数据
        
        问题：如果持仓的币种不在 coins_pick 选出的列表中，
        它们就不会有 market_data，导致止盈/止损策略无法计算正确的 PnL。
        
        解决：单独为这些持仓币种获取实时价格。
        """
        if not state.positions:
            return
        
        # 找出需要补充价格的持仓币种
        missing_symbols = []
        for pos in state.positions:
            symbol = pos.symbol
            # 检查是否已有价格数据
            data = state.market_data.get(symbol, {})
            indicators = data.get('indicators', {})
            current_price = indicators.get('current_price', 0)
            
            if current_price <= 0:
                missing_symbols.append(symbol)
        
        if not missing_symbols:
            return
        
        logger.info(f"🔄 Fetching realtime prices for {len(missing_symbols)} position symbols: {missing_symbols}")
        
        try:
            # 批量获取实时价格
            tickers = await self.market.trader.exchange.fetch_tickers(missing_symbols)
            
            for symbol in missing_symbols:
                if symbol in tickers:
                    ticker = tickers[symbol]
                    current_price = float(ticker.get('last') or ticker.get('close') or 0)
                    
                    if current_price > 0:
                        # 确保 market_data 中有这个币种的数据
                        if symbol not in state.market_data:
                            state.market_data[symbol] = {'indicators': {}}
                        if 'indicators' not in state.market_data[symbol]:
                            state.market_data[symbol]['indicators'] = {}
                        
                        state.market_data[symbol]['indicators']['current_price'] = current_price
                        logger.info(f"   ✅ {symbol}: ${current_price:.6f}")
                    else:
                        logger.warning(f"   ⚠️ {symbol}: price is 0")
                else:
                    logger.warning(f"   ⚠️ {symbol}: ticker not found")
                    
        except Exception as e:
            logger.error(f"Failed to fetch position prices: {e}")
            # Fallback: 尝试逐个获取
            for symbol in missing_symbols:
                try:
                    ticker = await self.market.trader.exchange.fetch_ticker(symbol)
                    current_price = float(ticker.get('last') or ticker.get('close') or 0)
                    
                    if current_price > 0:
                        if symbol not in state.market_data:
                            state.market_data[symbol] = {'indicators': {}}
                        if 'indicators' not in state.market_data[symbol]:
                            state.market_data[symbol]['indicators'] = {}
                        state.market_data[symbol]['indicators']['current_price'] = current_price
                        logger.info(f"   ✅ {symbol} (fallback): ${current_price:.6f}")
                except Exception as e2:
                    logger.error(f"   ❌ {symbol}: {e2}")
