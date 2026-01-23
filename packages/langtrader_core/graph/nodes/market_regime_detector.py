# packages/langtrader_core/graph/nodes/market_regime_detector.py
"""
市场状态识别节点 - 判断趋势/震荡/高波动

使用 market_state 节点已计算的指标（ADX, Bollinger Bands, EMA）
判断当前市场处于什么状态，决定后续策略分支：
- trending_up/down: 趋势市，正常进入 AI 决策
- ranging: 震荡市，跳过开仓或切换到网格策略
- volatile: 高波动，减小仓位或观望
"""
from langtrader_core.plugins.protocol import NodePlugin, NodeMetadata
from langtrader_core.graph.state import State
from langtrader_core.utils import get_logger
from typing import Dict, Any, List, Literal, Tuple, Optional

logger = get_logger("market_regime_detector")

# 市场状态类型定义
MarketRegime = Literal["trending_up", "trending_down", "ranging", "volatile", "uncertain"]


class MarketRegimeDetector(NodePlugin):
    """
    市场状态识别器
    
    使用 market_state 节点已计算的指标（ADX, Bollinger Bands, EMA）
    判断当前市场处于什么状态，决定后续策略分支。
    
    判断逻辑：
    1. BB 宽度 > 8% → 高波动 (volatile)
    2. ADX < 25 且 BB 宽度 < 3% → 震荡市 (ranging)
    3. ADX >= 25 → 趋势市 (trending_up / trending_down)
    4. 其他情况 → 不确定 (uncertain)
    """
    
    metadata = NodeMetadata(
        name="market_regime_detector",
        display_name="Market Regime Detector",
        version="1.0.0",
        author="LangTrader",
        description="识别市场状态（趋势/震荡/高波动），决定后续策略分支",
        category="analysis",
        tags=["regime", "trend", "filter"],
        inputs=["symbols", "market_data", "positions"],
        outputs=["market_regime", "regime_confidence", "regime_details"],
        requires=["market_state"],
        insert_after="market_state",
        suggested_order=3,  # 在 market_state(2) 之后，需要调整 quant_signal_filter 的顺序
        auto_register=True
    )
    
    # 默认配置（可通过 system_configs 数据库配置覆盖）
    DEFAULT_CONFIG = {
        "adx_trending_threshold": 25,        # ADX > 25 = 趋势市
        "bb_width_ranging_threshold": 0.03,  # BB宽度 < 3% = 震荡
        "bb_width_volatile_threshold": 0.08, # BB宽度 > 8% = 高波动
        "continue_if_has_positions": True,   # 有持仓时继续进入决策
        "primary_timeframe": "4h",           # 主要参考的时间框架
    }
    
    def __init__(self, context=None, config=None):
        """
        初始化市场状态识别器
        
        配置加载优先级：
        1. 传入的 config 参数（最高）
        2. system_configs 数据库配置
        3. DEFAULT_CONFIG 默认值（最低）
        """
        super().__init__(context, config)
        
        # 从数据库加载配置
        db_config = self.load_config_from_database('market_regime')
        
        # 合并配置
        self.node_config = {
            "adx_trending_threshold": db_config.get(
                'adx_trending_threshold', 
                self.DEFAULT_CONFIG['adx_trending_threshold']
            ),
            "bb_width_ranging_threshold": db_config.get(
                'bb_width_ranging_threshold', 
                self.DEFAULT_CONFIG['bb_width_ranging_threshold']
            ),
            "bb_width_volatile_threshold": db_config.get(
                'bb_width_volatile_threshold', 
                self.DEFAULT_CONFIG['bb_width_volatile_threshold']
            ),
            "continue_if_has_positions": db_config.get(
                'continue_if_has_positions', 
                self.DEFAULT_CONFIG['continue_if_has_positions']
            ),
            "primary_timeframe": db_config.get(
                'primary_timeframe', 
                self.DEFAULT_CONFIG['primary_timeframe']
            ),
        }
        
        # 传入的 config 参数优先级最高
        if config:
            self.node_config.update(config)
        
        logger.info(f"✅ MarketRegimeDetector initialized")
        logger.info(f"   ADX threshold: {self.node_config['adx_trending_threshold']}")
        logger.info(f"   BB ranging threshold: {self.node_config['bb_width_ranging_threshold']}")
        logger.info(f"   BB volatile threshold: {self.node_config['bb_width_volatile_threshold']}")
    
    async def run(self, state: State) -> State:
        """
        执行市场状态识别
        
        流程：
        1. 检查是否有持仓需要管理
        2. 分析每个候选币种的市场状态
        3. 聚合投票得出整体市场状态
        4. 写入 State 供下游节点使用
        """
        logger.info("=" * 60)
        logger.info("🔍 MarketRegimeDetector 开始执行")
        logger.info("=" * 60)
        
        # 检查是否有持仓
        has_positions = bool(state.positions)
        if has_positions:
            logger.info(f"📦 当前有 {len(state.positions)} 个持仓")
        
        # 收集各币种的判断
        regime_votes: List[Dict] = []
        details: List[Dict] = []
        
        for symbol in state.symbols:
            symbol_data = state.market_data.get(symbol, {})
            indicators = symbol_data.get('indicators', {})
            
            if not indicators:
                logger.warning(f"⚠️ {symbol}: 无指标数据，跳过")
                continue
            
            # 分析单个币种
            result = self._analyze_symbol(symbol, indicators)
            regime_votes.append(result)
            details.append({
                "symbol": symbol,
                "regime": result["regime"],
                "confidence": result["confidence"],
                "reason": result["reason"],
            })
        
        # 聚合判断整体市场状态
        overall_regime, overall_confidence = self._aggregate_regimes(regime_votes)
        
        # 写入 State
        state.market_regime = overall_regime
        state.regime_confidence = overall_confidence
        state.regime_details = details
        
        # 日志输出
        logger.info(f"📊 整体市场状态: {overall_regime} (置信度: {overall_confidence:.1%})")
        for d in details[:5]:  # 只显示前 5 个
            logger.info(f"   {d['symbol']}: {d['regime']} - {d['reason']}")
        
        # 根据市场状态给出建议
        if overall_regime == "ranging":
            if has_positions and self.node_config.get("continue_if_has_positions"):
                logger.warning("⏸️ 震荡市，但有持仓需要管理，继续进入决策")
            else:
                logger.warning("⏸️ 震荡市检测，建议跳过开仓或切换到网格策略")
        elif overall_regime == "volatile":
            logger.warning("⚠️ 高波动市检测，建议减小仓位或观望")
        else:
            logger.info(f"✅ {overall_regime} 市场，正常进入决策")
        
        logger.info("=" * 60)
        return state
    
    def _analyze_symbol(self, symbol: str, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析单个币种的市场状态
        
        Args:
            symbol: 币种符号
            indicators: 技术指标字典
            
        Returns:
            包含 regime, confidence, reason 的字典
        """
        tf = self.node_config["primary_timeframe"]
        
        # ========== 读取指标 ==========
        # ADX（趋势强度）- 优先使用配置的时间框架
        # 注意：ADX 返回的是字典 {'adx': float, 'plus_di': float, 'minus_di': float}
        adx_data = (
            indicators.get(f'adx_{tf}') or 
            indicators.get('adx_4h') or 
            indicators.get('adx_1d') or 
            {}
        )
        adx = adx_data.get('adx', 0) if isinstance(adx_data, dict) else 0
        
        # Bollinger Bands → 计算宽度
        bb = (
            indicators.get(f'bollinger_{tf}') or 
            indicators.get('bollinger_4h') or 
            {}
        )
        bb_width = self._calculate_bb_width(bb)
        
        # EMA 均线
        ema_20 = (
            indicators.get(f'ema_20_{tf}') or 
            indicators.get('ema_20_4h') or 
            0
        )
        ema_50 = (
            indicators.get(f'ema_50_{tf}') or 
            indicators.get('ema_50_4h') or 
            0
        )
        
        # 当前价格
        current_price = indicators.get('current_price', 0)
        
        # RSI（辅助判断）
        rsi = (
            indicators.get(f'rsi_{tf}') or 
            indicators.get('rsi_4h') or 
            indicators.get('rsi_3m') or 
            50
        )
        
        # ========== 阈值 ==========
        adx_threshold = self.node_config['adx_trending_threshold']
        bb_ranging = self.node_config['bb_width_ranging_threshold']
        bb_volatile = self.node_config['bb_width_volatile_threshold']
        
        # ========== 判断逻辑 ==========
        
        # 1. 高波动检测（优先级最高）
        if bb_width > bb_volatile:
            return {
                "regime": "volatile",
                "confidence": min(bb_width / 0.12, 1.0),
                "reason": f"BB宽度={bb_width:.1%} > {bb_volatile:.0%}"
            }
        
        # 2. 震荡市检测（低ADX + 窄BB）
        if adx < adx_threshold and bb_width < bb_ranging:
            confidence = 1 - (adx / adx_threshold) if adx_threshold > 0 else 0.5
            return {
                "regime": "ranging",
                "confidence": confidence,
                "reason": f"ADX={adx:.1f}<{adx_threshold}, BB={bb_width:.1%}<{bb_ranging:.0%}"
            }
        
        # 3. 趋势市检测（ADX >= 25）
        if adx >= adx_threshold:
            # 判断趋势方向
            if current_price > 0 and ema_20 > 0 and ema_50 > 0:
                if ema_20 > ema_50 and current_price > ema_20:
                    return {
                        "regime": "trending_up",
                        "confidence": min(adx / 50, 1.0),
                        "reason": f"ADX={adx:.1f}, EMA20>EMA50, 价格>EMA20"
                    }
                elif ema_20 < ema_50 and current_price < ema_20:
                    return {
                        "regime": "trending_down",
                        "confidence": min(adx / 50, 1.0),
                        "reason": f"ADX={adx:.1f}, EMA20<EMA50, 价格<EMA20"
                    }
            
            # ADX 高但方向不明确，用 RSI 辅助判断
            direction = "trending_up" if rsi > 50 else "trending_down"
            return {
                "regime": direction,
                "confidence": 0.5,
                "reason": f"ADX={adx:.1f}, 方向不明确(RSI={rsi:.0f})"
            }
        
        # 4. 不确定
        return {
            "regime": "uncertain",
            "confidence": 0.3,
            "reason": f"信号混合: ADX={adx:.1f}, BB={bb_width:.1%}, RSI={rsi:.0f}"
        }
    
    def _calculate_bb_width(self, bb: Dict[str, Any]) -> float:
        """
        计算布林带宽度
        
        Args:
            bb: 布林带数据字典，包含 upper, middle, lower
            
        Returns:
            布林带宽度（百分比）
        """
        if not isinstance(bb, dict):
            return 0.05  # 默认值
        
        upper = bb.get('upper', 0)
        lower = bb.get('lower', 0)
        middle = bb.get('middle', 0)
        
        if middle > 0 and upper > 0 and lower > 0:
            return (upper - lower) / middle
        
        return 0.05  # 默认值
    
    def _aggregate_regimes(self, votes: List[Dict]) -> Tuple[MarketRegime, float]:
        """
        聚合多币种判断，得出整体市场状态
        
        使用加权投票机制：
        - 统计各状态的票数和置信度总和
        - 选择置信度总和最高的状态
        
        Args:
            votes: 各币种的判断结果列表
            
        Returns:
            (整体市场状态, 平均置信度) 元组
        """
        if not votes:
            return "uncertain", 0.0
        
        # 统计投票
        regime_scores: Dict[str, Dict] = {}
        for vote in votes:
            regime = vote["regime"]
            confidence = vote["confidence"]
            if regime not in regime_scores:
                regime_scores[regime] = {"count": 0, "total_conf": 0}
            regime_scores[regime]["count"] += 1
            regime_scores[regime]["total_conf"] += confidence
        
        # 找得分最高的状态
        best = max(regime_scores.items(), key=lambda x: x[1]["total_conf"])
        regime_name = best[0]
        avg_conf = best[1]["total_conf"] / best[1]["count"] if best[1]["count"] > 0 else 0
        
        return regime_name, avg_conf
