# packages/langtrader_core/services/quant_signal.py
"""
量化信号计算服务
基于规则的技术分析信号评分系统
"""
from typing import Dict, Any
from langtrader_core.utils import get_logger

logger = get_logger("quant_signal")


class QuantSignalCalculator:
    """量化信号计算器（基于规则）"""
    
    @staticmethod
    def calculate_trend_score(indicators: Dict) -> Dict[str, Any]:
        """计算趋势得分 (0-100)"""
        score = 0
        reasons = []
        
        current_price = indicators.get('current_price', 0)
        ema_20_3m = indicators.get('ema_20_3m', 0)
        ema_20_4h = indicators.get('ema_20_4h', 0)
        ema_50_4h = indicators.get('ema_50_4h', 0)
        ema_200_4h = indicators.get('ema_200_4h', 0)
        
        # 多时间框架 EMA 排列
        if current_price > ema_20_3m > ema_20_4h:
            score += 30
            reasons.append("多头EMA排列(3m+4h)")
        elif current_price < ema_20_3m < ema_20_4h:
            score -= 20
            reasons.append("空头EMA排列")
        
        # 4h 长期趋势
        if ema_20_4h > ema_50_4h > ema_200_4h:
            score += 20
            reasons.append("4h长期多头趋势")
        
        # 价格位置
        if current_price > ema_200_4h:
            score += 10
            reasons.append("价格高于200EMA")
        
        return {
            "score": max(0, min(100, score + 50)),  # 基准分50
            "reasons": reasons
        }
    
    @staticmethod
    def calculate_momentum_score(indicators: Dict) -> Dict[str, Any]:
        """计算动量得分"""
        score = 0
        reasons = []
        
        macd_3m = indicators.get('macd_3m', 0)
        macd_4h = indicators.get('macd_4h', 0)
        rsi_3m = indicators.get('rsi_3m', 50)
        rsi_4h = indicators.get('rsi_4h', 50)
        
        # MACD 状态
        if macd_3m > 0 and macd_4h > 0:
            score += 25
            reasons.append("MACD双周期多头")
        elif macd_3m < 0 and macd_4h < 0:
            score -= 20
            reasons.append("MACD双周期空头")
        
        # RSI 健康区间
        if 40 < rsi_3m < 70 and 40 < rsi_4h < 70:
            score += 15
            reasons.append("RSI健康区间")
        elif rsi_3m > 80 or rsi_4h > 80:
            score -= 25
            reasons.append("RSI超买(>80)")
        elif rsi_3m < 20 or rsi_4h < 20:
            score -= 15
            reasons.append("RSI超卖(<20)")
        
        # Stochastic 确认
        stoch_3m = indicators.get('stochastic_3m', {})
        if stoch_3m:
            k, d = stoch_3m.get('k', 50), stoch_3m.get('d', 50)
            if k > d and k < 80:
                score += 10
                reasons.append("Stoch金叉且未超买")
        
        return {
            "score": max(0, min(100, score + 50)),
            "reasons": reasons
        }
    
    @staticmethod
    def calculate_volume_score(indicators: Dict) -> Dict[str, Any]:
        """计算量能得分"""
        score = 0
        reasons = []
        
        volume_ratio_3m = indicators.get('volume_ratio_3m', 1.0)
        obv_3m = indicators.get('obv_3m', 0)
        obv_4h = indicators.get('obv_4h', 0)
        
        # 成交量放大
        if volume_ratio_3m > 1.5:
            score += 30
            reasons.append(f"成交量放大{volume_ratio_3m:.1f}倍")
        elif volume_ratio_3m < 0.7:
            score -= 20
            reasons.append("成交量萎缩(量价背离)")
        
        # OBV 趋势
        if obv_3m > 0 and obv_4h > 0:
            score += 20
            reasons.append("OBV资金流入")
        
        return {
            "score": max(0, min(100, score + 50)),
            "reasons": reasons
        }
    
    @staticmethod
    def calculate_sentiment_score(indicators: Dict) -> Dict[str, Any]:
        """计算市场情绪得分（基于资金费率）"""
        score = 50  # 中性基准
        reasons = []
        
        funding_rate = indicators.get('funding_rate', 0)
        
        if funding_rate is None or funding_rate == 0:
            return {"score": 50, "reasons": ["无资金费率数据"]}
        
        # 资金费率解读
        if -0.01 < funding_rate < 0.05:
            score = 70
            reasons.append(f"健康资金费率({funding_rate*100:.3f}%)")
        elif funding_rate > 0.1:
            score = 30
            reasons.append(f"多头过热(费率{funding_rate*100:.3f}%)")
        elif funding_rate < -0.05:
            score = 80
            reasons.append(f"空头过度(费率{funding_rate*100:.3f}%，做多机会)")
        
        return {"score": score, "reasons": reasons}
    
    # 默认权重配置
    DEFAULT_WEIGHTS = {
        "trend": 0.4,
        "momentum": 0.3,
        "volume": 0.2,
        "sentiment": 0.1
    }
    
    @staticmethod
    def calculate_composite_score(
        indicators: Dict,
        weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """计算综合得分"""
        
        # 防护：确保 weights 不为 None
        if weights is None:
            weights = QuantSignalCalculator.DEFAULT_WEIGHTS
        
        # 计算各维度得分
        trend = QuantSignalCalculator.calculate_trend_score(indicators)
        momentum = QuantSignalCalculator.calculate_momentum_score(indicators)
        volume = QuantSignalCalculator.calculate_volume_score(indicators)
        sentiment = QuantSignalCalculator.calculate_sentiment_score(indicators)
        
        # 加权计算
        total_score = (
            trend['score'] * weights.get('trend', 0.4) +
            momentum['score'] * weights.get('momentum', 0.3) +
            volume['score'] * weights.get('volume', 0.2) +
            sentiment['score'] * weights.get('sentiment', 0.1)
        )
        
        # 合并原因
        all_reasons = (
            trend['reasons'] + 
            momentum['reasons'] + 
            volume['reasons'] + 
            sentiment['reasons']
        )
        
        return {
            "total_score": round(total_score, 1),
            "breakdown": {
                "trend": trend['score'],
                "momentum": momentum['score'],
                "volume": volume['score'],
                "sentiment": sentiment['score']
            },
            "reasons": all_reasons,
            "pass_filter": total_score >= 50  # 默认阈值
        }

