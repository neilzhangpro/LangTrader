# packages/langtrader_core/graph/nodes/quant_signal_filter.py
"""
量化信号预处理节点
在 LLM 分析前对市场数据进行量化评分和过滤
"""
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import State
from langtrader_core.services.quant_signal import QuantSignalCalculator
from langtrader_core.utils import get_logger

logger = get_logger("quant_signal_filter")


class QuantSignalFilter(NodePlugin):
    """量化信号预处理节点"""
    
    metadata = NodeMetadata(
        name="quant_signal_filter",
        display_name="Quantitative Signal Filter",
        version="1.0.0",
        author="LangTrader official",
        description="量化信号预处理和过滤",
        category="analysis",
        tags=["quantitative", "signal", "filter"],
        insert_after="market_state",
        suggested_order=3,
        auto_register=True
    )
    
    def __init__(self, context=None, config=None):
        super().__init__(context, config)
        self.calculator = QuantSignalCalculator()
        
        # 从 bot config 读取配置（通过 context）
        self.weights = config.get('quant_signal_weights') if config else {
            "trend": 0.4,
            "momentum": 0.3,
            "volume": 0.2,
            "sentiment": 0.1
        }
        self.threshold = config.get('quant_signal_threshold', 50)
    
    async def run(self, state: State) -> State:
        """为每个币种计算量化信号"""
        
        logger.info(f"🔍 Calculating quantitative signals for {len(state.symbols)} symbols")
        logger.info(f"   Weights: {self.weights}")
        logger.info(f"   Threshold: {self.threshold}")
        
        filtered_symbols = []
        
        for symbol in state.symbols:
            symbol_data = state.market_data.get(symbol, {})
            indicators = symbol_data.get('indicators', {})
            
            if not indicators:
                logger.warning(f"⚠️ {symbol}: No indicators, skipping")
                continue  # 无指标直接跳过（回测和实盘一致）
            
            # 计算量化信号
            signal = self.calculator.calculate_composite_score(
                indicators, 
                self.weights
            )
            
            # 保存到 indicators 字典，供 decision.py 读取
            symbol_data['indicators']['quant_signal'] = signal
            
            # 统一过滤逻辑（回测和实盘一致，确保回测结果可靠）
            if signal['total_score'] >= self.threshold:
                filtered_symbols.append(symbol)
                logger.info(f"✅ {symbol}: Score={signal['total_score']:.1f} PASS")
            else:
                logger.info(f"❌ {symbol}: Score={signal['total_score']:.1f} FILTERED OUT")
        
        # 更新 symbols 列表（只保留通过过滤的）
        original_count = len(state.symbols)
        state.symbols = filtered_symbols
        
        logger.info(
            f"✅ Quantitative filter: {len(filtered_symbols)}/{original_count} passed"
        )
        
        return state

