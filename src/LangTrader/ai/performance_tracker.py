# src/LangTrader/performance_tracker.py

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.LangTrader.utils import logger

class RealTimePerformanceTracker:
    """实时性能追踪器"""
    
    def __init__(self, trader_id: str, db):
        self.trader_id = trader_id
        self.db = db
    
    def record_snapshot(self, account_balance: dict, decision_id: str = None):
        """记录权益快照（每次决策后调用）"""
        margin_summary = account_balance.get('marginSummary', {})
        
        equity = float(margin_summary.get('accountValue', 0))
        withdrawable = float(account_balance.get('withdrawable', 0))
        margin_used = float(margin_summary.get('totalMarginUsed', 0))
        
        positions = account_balance.get('assetPositions', [])
        open_positions = len(positions)
        total_position_value = float(margin_summary.get('totalNtlPos', 0))
        
        # 计算总实现盈亏
        closed_pnl = self.db.execute("""
            SELECT COALESCE(SUM(realized_pnl), 0) as total
            FROM positions
            WHERE trader_id = %s AND status = 'closed'
        """, (self.trader_id,))[0]['total']
        
        # 记录快照
        self.db.execute("""
            INSERT INTO equity_history
            (trader_id, equity, withdrawable, margin_used,
             open_positions, total_position_value, 
             realized_pnl_total, decision_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (self.trader_id, equity, withdrawable, margin_used,
              open_positions, total_position_value, closed_pnl, decision_id))
    
    def calculate_real_time_metrics(self, lookback_days: int = 30) -> dict:
        """计算实时性能指标"""
        
        # 计算起始时间
        start_time = datetime.now() - timedelta(days=lookback_days)
        
        # 1. 获取权益历史（修复SQL占位符问题）
        equity_data = self.db.execute("""
            SELECT timestamp, equity
            FROM equity_history
            WHERE trader_id = %s
            AND timestamp >= %s
            ORDER BY timestamp
        """, (self.trader_id, start_time))
        
        logger.info(f"📊 查询到 {len(equity_data)} 条权益记录（{lookback_days}天内）")
        
        if len(equity_data) < 2:
            logger.warning(f"⚠️ 权益历史记录不足（{len(equity_data)}条<2），无法计算性能指标")
            return self._default_metrics()
        
        logger.info(f"✅ 权益数据充足，开始计算性能指标...")
        
        # 🔧 转换 Decimal 为 float，避免类型错误
        equity_data_clean = [
            {'timestamp': row['timestamp'], 'equity': float(row['equity'])}
            for row in equity_data
        ]
        df = pd.DataFrame(equity_data_clean)
        
        # 2. 计算夏普率
        returns = df['equity'].pct_change().dropna()
        if len(returns) > 0 and returns.std() > 0:
            # 假设每5分钟一个快照（或根据实际决策频率调整）
            # 你的是5分钟一次，一天288次，一年105120次
            periods_per_year = 365 * 288
            sharpe_ratio = (returns.mean() - 0) / returns.std() * np.sqrt(periods_per_year)
        else:
            sharpe_ratio = 0.0
        
        # 3. 计算最大回撤和当前回撤
        equity_series = df['equity']
        running_max = equity_series.cummax()
        drawdown_series = (equity_series - running_max) / running_max
        max_drawdown = float(drawdown_series.min())
        current_drawdown = float(drawdown_series.iloc[-1])
        
        # 4. 获取交易统计（转换 Decimal 为 float）
        positions = self.db.execute("""
            SELECT * FROM positions
            WHERE trader_id = %s AND status = 'closed'
            ORDER BY closed_at DESC
        """, (self.trader_id,))
        
        total_trades = len(positions)
        winning_trades = sum(1 for p in positions if float(p['realized_pnl']) > 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        total_pnl = sum(float(p['realized_pnl']) for p in positions)
        
        # 5. 判断性能状态
        performance_status = self._judge_performance_status(
            sharpe_ratio, win_rate, current_drawdown
        )
        
        risk_level = self._judge_risk_level(
            current_drawdown, max_drawdown
        )
        
        metrics = {
            'total_trades': total_trades,
            'win_rate': float(win_rate),
            'total_pnl': float(total_pnl),
            'sharpe_ratio': float(sharpe_ratio),
            'max_drawdown': float(max_drawdown),
            'current_drawdown': float(current_drawdown),
            'performance_status': performance_status,
            'risk_level': risk_level,
            'lookback_days': lookback_days
        }
        
        # 6. 更新缓存
        self._update_cache(metrics)
        
        return metrics
    
    def _judge_performance_status(self, sharpe: float, win_rate: float, drawdown: float) -> str:
        """判断性能状态"""
        if sharpe > 2.0 and win_rate > 0.6:
            return "excellent"  # 优秀
        elif sharpe > 1.0 and win_rate > 0.5:
            return "good"       # 良好
        elif sharpe > 0.5 or win_rate > 0.45:
            return "fair"       # 一般
        elif drawdown < -0.15:
            return "danger"     # 危险（大幅回撤）
        else:
            return "poor"       # 较差
    
    def _judge_risk_level(self, current_dd: float, max_dd: float) -> str:
        """判断风险水平"""
        if current_dd < -0.15:
            return "high"       # 高风险
        elif current_dd < -0.08:
            return "medium"     # 中风险
        else:
            return "low"        # 低风险
    
    def _default_metrics(self) -> dict:
        """返回默认指标（无历史数据时）"""
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'current_drawdown': 0.0,
            'performance_status': 'unknown',
            'risk_level': 'low',
            'lookback_days': 0
        }
    
    def _update_cache(self, metrics: dict):
        """更新性能缓存"""
        try:
            self.db.execute("""
                INSERT INTO performance_cache 
                (trader_id, total_trades, win_rate, total_pnl,
                 sharpe_ratio, max_drawdown, current_drawdown,
                 performance_status, risk_level, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (trader_id) 
                DO UPDATE SET
                    total_trades = EXCLUDED.total_trades,
                    win_rate = EXCLUDED.win_rate,
                    total_pnl = EXCLUDED.total_pnl,
                    sharpe_ratio = EXCLUDED.sharpe_ratio,
                    max_drawdown = EXCLUDED.max_drawdown,
                    current_drawdown = EXCLUDED.current_drawdown,
                    performance_status = EXCLUDED.performance_status,
                    risk_level = EXCLUDED.risk_level,
                    last_updated = NOW()
            """, (self.trader_id, metrics['total_trades'], metrics['win_rate'],
                  metrics['total_pnl'], metrics['sharpe_ratio'], 
                  metrics['max_drawdown'], metrics['current_drawdown'],
                  metrics['performance_status'], metrics['risk_level']))
        except Exception as e:
            logger.warning(f"⚠️ 更新性能缓存失败（表可能不存在）: {e}")
    
    def get_performance_signal(self, metrics: dict = None) -> str:
        """生成性能信号文本（注入提示词）"""
        if metrics is None:
            metrics = self.calculate_real_time_metrics()
        
        # 安全获取，避免KeyError
        performance_status = metrics.get('performance_status', 'unknown')
        risk_level = metrics.get('risk_level', 'low')
        
        status_emoji = {
            "excellent": "🔥",
            "good": "✅",
            "fair": "⚠️",
            "poor": "🔴",
            "danger": "🚨",
            "unknown": "❓"
        }.get(performance_status, "❓")
        
        risk_emoji = {
            "low": "✅",
            "medium": "⚠️",
            "high": "🚨"
        }.get(risk_level, "✅")
        
        signal = f"""
=== 📊 实时性能指标（当前表现）===

**整体表现：** {status_emoji} {performance_status.upper()}
**风险水平：** {risk_emoji} {risk_level.upper()}

📈 关键指标（近{metrics.get('lookback_days', 0)}天）：
- 夏普率: {metrics.get('sharpe_ratio', 0):.2f}
- 最大回撤: {metrics.get('max_drawdown', 0):.1%}
- 当前回撤: {metrics.get('current_drawdown', 0):.1%}
- 胜率: {metrics.get('win_rate', 0):.1%}
- 累计盈亏: ${metrics.get('total_pnl', 0):.2f}

💡 **性能信号解读：**
"""
        
        # 根据性能状态给出建议
        if performance_status == 'excellent':
            signal += """
- ✅ 当前表现优异，策略运行良好
- ✅ 可保持当前交易频率和仓位规模
- ✅ 夏普率>2表示风险调整后收益出色
"""
        
        elif performance_status == 'good':
            signal += """
- ✅ 当前表现良好，继续保持
- ⚠️ 注意控制回撤，不要过度激进
"""
        
        elif performance_status == 'fair':
            signal += """
- ⚠️ 当前表现一般，需要提高门槛
- 建议：只在信号明确度'高'时交易
- 建议：降低杠杆至1-2倍
"""
        
        elif performance_status == 'poor':
            signal += """
- 🔴 当前表现较差，需要调整策略
- 建议：大幅提高交易门槛（信号>70%）
- 建议：杠杆降至1倍
- 建议：减少交易频率，观察为主
"""
        
        elif performance_status == 'danger':
            signal += f"""
- 🚨 警告：当前回撤{metrics.get('current_drawdown', 0):.1%}，已达危险水平
- **强烈建议：暂停交易，等待回撤恢复**
- **或者：极度谨慎，仅在绝对确定的机会时交易**
"""
        
        # 根据风险水平给出仓位建议
        signal += f"\n**风险控制建议：**\n"
        
        if risk_level == 'high':
            signal += "- 🚨 当前处于高风险状态，建议降低仓位至平时的50%\n"
        elif risk_level == 'medium':
            signal += "- ⚠️ 当前风险适中，保持正常仓位\n"
        else:
            signal += "- ✅ 当前风险较低，可考虑正常或略增仓位\n"
        
        return signal