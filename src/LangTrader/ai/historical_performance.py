from src.LangTrader.utils import logger
from src.LangTrader.config import Config
from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from src.LangTrader.market import CryptoFetcher
from collections import defaultdict
from datetime import datetime
import json

class HistoricalPerformance:
    def __init__(self,config:Config):
        self.config = config
        self.hyperliquid = hyperliquidAPI()
        self.fetcher = CryptoFetcher()
        self.db = config.db
        self.symbols = config.symbols

    def get_coin_performance_analysis(self,trader_id:str):
        """
        analyze the performance of the coin
        returns:
        dict: {
            'BTC': {
                'win_rate': 0.75,
                'avg_profit':2.5,
                'consecutive_wins':3,
                'status':'excellent'
            }
        }
        
        """
        logger.info("---start coin performance analysis")
        #get rencent 20 trade of close position
        recent_positions = self.db.execute("""
            SELECT symbol, realized_pnl, entry_price, exit_price, side, 
                   opened_at, closed_at
            FROM positions
            WHERE trader_id = %s
            AND status = 'closed'
            ORDER BY closed_at DESC
            LIMIT 20
        """, (trader_id,))

        if not recent_positions:
            logger.warning("No history trade data")
            return {}

        
        # 按币种分组统计
        coin_stats = defaultdict(lambda: {
            'trades': [],
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0,
            'consecutive': 0  # 正数=连胜，负数=连败
        })
        
        for pos in recent_positions:
            symbol = pos['symbol']
            pnl = float(pos['realized_pnl'])
            
            # 计算盈利百分比
            entry = float(pos['entry_price'])
            exit_price = float(pos.get('exit_price', entry))
            if entry > 0:
                pnl_pct = ((exit_price - entry) / entry) * 100
                if pos['side'] == 'short':
                    pnl_pct = -pnl_pct
            else:
                pnl_pct = 0.0
            
            coin_stats[symbol]['trades'].append({
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'is_win': pnl > 0
            })
            
            if pnl > 0:
                coin_stats[symbol]['wins'] += 1
            else:
                coin_stats[symbol]['losses'] += 1
            
            coin_stats[symbol]['total_pnl'] += pnl
        
        # 计算每个币种的详细指标
        analysis_result = {}
        for symbol, stats in coin_stats.items():
            total = len(stats['trades'])
            wins = stats['wins']
            losses = stats['losses']
            win_rate = wins / total if total > 0 else 0
            
            # 计算平均盈利/亏损百分比
            win_pcts = [t['pnl_pct'] for t in stats['trades'] if t['is_win']]
            loss_pcts = [t['pnl_pct'] for t in stats['trades'] if not t['is_win']]
            
            avg_profit = sum(win_pcts) / len(win_pcts) if win_pcts else 0
            avg_loss = sum(loss_pcts) / len(loss_pcts) if loss_pcts else 0
            
            # 计算连续胜/亏
            consecutive_wins = 0
            consecutive_losses = 0
            current_streak = 0
            
            for trade in reversed(stats['trades']):  # 从最早到最近
                if trade['is_win']:
                    if current_streak >= 0:
                        current_streak += 1
                    else:
                        current_streak = 1
                else:
                    if current_streak <= 0:
                        current_streak -= 1
                    else:
                        current_streak = -1
            
            if current_streak > 0:
                consecutive_wins = current_streak
            else:
                consecutive_losses = abs(current_streak)
            
            # 判断状态
            if consecutive_losses >= 3:
                status = '🔴 危险'
                advice = f'连续{consecutive_losses}次止损，建议暂停交易或大幅降低仓位'
            elif win_rate >= 0.7:
                status = '✅ 优秀'
                advice = f'近期表现最佳，可适度加大仓位'
            elif win_rate >= 0.5:
                status = '⚠️ 一般'
                advice = '表现中等，保持当前仓位'
            else:
                status = '🔴 较差'
                advice = '胜率偏低，建议谨慎交易'
            
            analysis_result[symbol] = {
                'total_trades': total,
                'win_rate': win_rate,
                'avg_profit_pct': avg_profit,
                'avg_loss_pct': avg_loss,
                'consecutive_wins': consecutive_wins,
                'consecutive_losses': consecutive_losses,
                'total_pnl': stats['total_pnl'],
                'status': status,
                'advice': advice
            }
            
            # 更新到数据库
            self.db.execute("""
                INSERT INTO coin_performance_analysis 
                (trader_id, symbol, total_trades, winning_trades, losing_trades,
                 win_rate, avg_profit_pct, avg_loss_pct, consecutive_wins, 
                 consecutive_losses, total_pnl, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (trader_id, symbol) 
                DO UPDATE SET
                    total_trades = EXCLUDED.total_trades,
                    winning_trades = EXCLUDED.winning_trades,
                    losing_trades = EXCLUDED.losing_trades,
                    win_rate = EXCLUDED.win_rate,
                    avg_profit_pct = EXCLUDED.avg_profit_pct,
                    avg_loss_pct = EXCLUDED.avg_loss_pct,
                    consecutive_wins = EXCLUDED.consecutive_wins,
                    consecutive_losses = EXCLUDED.consecutive_losses,
                    total_pnl = EXCLUDED.total_pnl,
                    last_updated = NOW()
            """, (trader_id, symbol, total, wins, losses, win_rate, 
                  avg_profit, avg_loss, consecutive_wins, consecutive_losses,
                  stats['total_pnl']))
        
        logger.info(f"✅ 币种表现分析完成，共分析 {len(analysis_result)} 个币种")
        return analysis_result
        

    def generate_smart_guidance(self, coin_analysis: dict) -> str:
        """
        🆕 生成智能指导文本
        """
        if not coin_analysis:
            return "暂无历史数据，建议小仓位试探"
        
        guidance_parts = ["📊 历史表现分析：\n"]
        
        # 找出最佳和最差币种
        best_coin = max(coin_analysis.items(), key=lambda x: x[1]['win_rate'])
        worst_coin = min(coin_analysis.items(), key=lambda x: x[1]['win_rate'])
        
        # 找出连续亏损的币种
        danger_coins = [
            (symbol, data) for symbol, data in coin_analysis.items()
            if data['consecutive_losses'] >= 3
        ]
        
        for symbol, data in coin_analysis.items():
            guidance_parts.append(
                f"• {symbol}: 胜率{data['win_rate']:.0%}, "
                f"平均盈利{data['avg_profit_pct']:+.1f}%, "
                f"{'连胜' if data['consecutive_wins'] > 0 else '连亏'}"
                f"{max(data['consecutive_wins'], data['consecutive_losses'])}次 "
                f"{data['status']}"
            )
        
        guidance_parts.append("\n💡 交易建议：")
        
        if danger_coins:
            for symbol, data in danger_coins:
                guidance_parts.append(
                    f"⚠️ {symbol}连续{data['consecutive_losses']}次止损，"
                    f"建议暂停交易或大幅降低仓位"
                )
        
        guidance_parts.append(
            f"✅ {best_coin[0]}近期表现最佳"
            f"（胜率{best_coin[1]['win_rate']:.0%}），可适度加大仓位"
        )
        
        # 判断市场状态
        avg_win_rate = sum(d['win_rate'] for d in coin_analysis.values()) / len(coin_analysis)
        if avg_win_rate > 0.6:
            market_state = "📈 当前可能处于趋势市，可适当延长持仓时间"
        elif avg_win_rate < 0.4:
            market_state = "📉 当前市场较难，建议降低交易频率，减小仓位"
        else:
            market_state = "🔄 当前市场震荡，建议快进快出"
        
        guidance_parts.append(market_state)
        
        return "\n".join(guidance_parts)
    
    def analyze_recent_losses(self, trader_id: str) -> list:
        """
        分析最近亏损交易的共同模式
        
        Returns:
            失败模式列表
        """
        patterns = []
        
        # 从数据库查询最近5次亏损交易
        recent_losses = self.db.execute("""
            SELECT p.symbol, p.side, p.entry_price, p.exit_price, 
                   p.realized_pnl, p.leverage, d.llm_analysis, d.confidence,
                   p.opened_at, p.closed_at
            FROM positions p
            LEFT JOIN decisions d ON p.decision_id = d.id
            WHERE p.trader_id = %s
            AND p.status = 'closed'
            AND p.realized_pnl < 0
            ORDER BY p.closed_at DESC
            LIMIT 5
        """, (trader_id,))
        
        if not recent_losses or len(recent_losses) < 2:
            return patterns
        
        # 1. 分析信号强度模式
        low_confidence_losses = [
            l for l in recent_losses 
            if l.get('confidence') and l.get('confidence') < 0.6
        ]
        if len(low_confidence_losses) >= 3:
            avg_conf = sum(l['confidence'] for l in low_confidence_losses) / len(low_confidence_losses)
            patterns.append(
                f"低置信度交易容易亏损（{len(low_confidence_losses)}次，"
                f"平均置信度{avg_conf:.0%}），建议提高交易门槛至70%以上"
            )
        
        # 2. 分析时间模式（快速止损 vs 长期持有）
        holding_times = []
        for loss in recent_losses:
            if loss.get('opened_at') and loss.get('closed_at'):
                duration = (loss['closed_at'] - loss['opened_at']).total_seconds() / 3600
                holding_times.append(duration)
        
        if holding_times and len(holding_times) >= 3:
            avg_holding = sum(holding_times) / len(holding_times)
            if avg_holding < 4:  # 小于4小时
                patterns.append(
                    f"亏损交易平均持仓{avg_holding:.1f}小时（快速止损），"
                    "市场波动剧烈，考虑降低交易频率或扩大止损范围"
                )
            elif avg_holding > 24:  # 大于24小时
                patterns.append(
                    f"亏损交易平均持仓{avg_holding:.1f}小时（长期持有），"
                    "止损设置过宽，建议收紧止损至3-4%"
                )
        
        # 3. 分析方向偏好（多空偏差）
        long_losses = [l for l in recent_losses if l['side'] == 'long']
        short_losses = [l for l in recent_losses if l['side'] == 'short']
        
        if len(long_losses) >= 4:
            patterns.append(
                f"最近多单亏损较多（{len(long_losses)}/{len(recent_losses)}次），"
                "当前可能处于下跌趋势，优先考虑做空机会"
            )
        elif len(short_losses) >= 4:
            patterns.append(
                f"最近空单亏损较多（{len(short_losses)}/{len(recent_losses)}次），"
                "当前可能处于上涨趋势，避免逆势做空"
            )
        
        # 4. 分析杠杆使用
        high_leverage_losses = [l for l in recent_losses if l.get('leverage', 1) >= 4]
        if len(high_leverage_losses) >= 3:
            patterns.append(
                f"高杠杆交易（≥4倍）亏损{len(high_leverage_losses)}次，"
                "建议降低杠杆至2-3倍以控制风险"
            )
        
        return patterns
    
    def analyze_recent_wins(self, trader_id: str) -> list:
        """
        分析最近盈利交易的共同模式
        
        Returns:
            成功模式列表
        """
        patterns = []
        
        # 从数据库查询最近5次盈利交易
        recent_wins = self.db.execute("""
            SELECT p.symbol, p.side, p.entry_price, p.exit_price, 
                   p.realized_pnl, p.leverage, d.llm_analysis, d.confidence,
                   d.indicators, p.opened_at, p.closed_at
            FROM positions p
            LEFT JOIN decisions d ON p.decision_id = d.id
            WHERE p.trader_id = %s
            AND p.status = 'closed'
            AND p.realized_pnl > 0
            ORDER BY p.closed_at DESC
            LIMIT 5
        """, (trader_id,))
        
        if not recent_wins or len(recent_wins) < 2:
            return patterns
        
        # 1. 分析盈利方向
        long_wins = [w for w in recent_wins if w['side'] == 'long']
        short_wins = [w for w in recent_wins if w['side'] == 'short']
        
        if len(long_wins) >= 4:
            avg_pnl = sum(float(w['realized_pnl']) for w in long_wins) / len(long_wins)
            patterns.append(
                f"多单成功率高（{len(long_wins)}/{len(recent_wins)}次盈利，"
                f"平均+${avg_pnl:.2f}），优先考虑做多机会"
            )
        elif len(short_wins) >= 4:
            avg_pnl = sum(float(w['realized_pnl']) for w in short_wins) / len(short_wins)
            patterns.append(
                f"空单成功率高（{len(short_wins)}/{len(recent_wins)}次盈利，"
                f"平均+${avg_pnl:.2f}），优先考虑做空机会"
            )
        
        # 2. 分析持仓时间
        holding_times = []
        for win in recent_wins:
            if win.get('opened_at') and win.get('closed_at'):
                duration = (win['closed_at'] - win['opened_at']).total_seconds() / 3600
                holding_times.append(duration)
        
        if holding_times and len(holding_times) >= 3:
            avg_holding = sum(holding_times) / len(holding_times)
            if avg_holding < 8:
                patterns.append(
                    f"短线交易（平均{avg_holding:.1f}小时）盈利效果好，"
                    "继续保持快进快出策略，盈利后及时止盈"
                )
            elif avg_holding > 24:
                patterns.append(
                    f"中长线交易（平均{avg_holding:.1f}小时）盈利效果好，"
                    "可适当延长盈利持仓时间，让利润奔跑"
                )
        
        # 3. 分析置信度
        high_conf_wins = [w for w in recent_wins if w.get('confidence') and w.get('confidence') > 0.7]
        if len(high_conf_wins) >= 4:
            patterns.append(
                f"高置信度交易（>70%）成功率高（{len(high_conf_wins)}/{len(recent_wins)}次），"
                "继续保持高标准选币，低置信度交易谨慎"
            )
        
        # 4. 分析币种集中度
        symbol_counts = {}
        for win in recent_wins:
            symbol = win['symbol']
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        
        dominant_symbol = max(symbol_counts.items(), key=lambda x: x[1]) if symbol_counts else None
        if dominant_symbol and dominant_symbol[1] >= 3:
            patterns.append(
                f"{dominant_symbol[0]}盈利次数最多（{dominant_symbol[1]}次），"
                "该币种表现优异，继续关注"
            )
        
        return patterns

    def get_20_decision_info(self,trader_id:str):
        logger.info("-----Start Get 20 Decision Info------")
        recent_decisions = self.db.execute("""
        SELECT * FROM decisions
        WHERE trader_id = %s
        ORDER BY created_at DESC
        LIMIT 3
        """,(trader_id,))
        if not recent_decisions:
            logger.warning("No recent decisions found")
            return None
        prompt_info = ""
        for decision in recent_decisions:
            prompt_info += f"Symbol: {decision['symbol']}\nAction: {decision['action']}\\nConfidence: {decision['confidence']}"
            llmanalysis = decision['llm_analysis']
            prompt_info +=f"决策结果: {llmanalysis}\n决策时间: {decision['created_at']}\n"
        return prompt_info

    def check_trading_frequency(self, trader_id: str) -> dict:
        """检查交易频率（防止过度交易）"""
        
        # 检查最近1小时交易次数
        recent_hour = self.db.execute("""
            SELECT COUNT(*) as count FROM positions
            WHERE trader_id = %s
            AND opened_at >= NOW() - INTERVAL '1 hour'
        """, (trader_id,))
        
        count = recent_hour[0]['count'] if recent_hour else 0
        
        if count >= 2:
            return {
                "allowed": False,
                "forced_hold": True,
                "message": f"🚨 最近1小时已交易{count}次（上限2次），本次决策必须选择 HOLD"
            }
        elif count >= 1:
            return {
                "allowed": True,
                "forced_hold": False,
                "message": f"⚠️ 已在1小时内交易{count}次，本次开仓需要极高置信度（>90%）"
            }
        else:
            return {
                "allowed": True,
                "forced_hold": False,
                "message": "✅ 交易频率正常，可考虑开仓"
            }
    
    def check_consecutive_stop_loss(self, trader_id: str) -> dict:
        """检查连续止损情况（实现暂停机制）"""
        
        # 获取最近5次已平仓交易
        recent_closed = self.db.execute("""
            SELECT closed_at, realized_pnl
            FROM positions
            WHERE trader_id = %s
            AND status = 'closed'
            ORDER BY closed_at DESC
            LIMIT 5
        """, (trader_id,))
        
        if not recent_closed or len(recent_closed) < 2:
            return {
                "forced_hold": False,
                "message": ""
            }
        
        # 判断连续止损
        consecutive_losses = 0
        for i, pos in enumerate(recent_closed):
            pnl = float(pos['realized_pnl'])
            if pnl < 0:
                if i == consecutive_losses:
                    consecutive_losses += 1
                else:
                    break
            else:
                break
        
        if consecutive_losses >= 4:
            # 检查距离最后一次止损的时间
            last_loss_time = recent_closed[0]['closed_at']
            hours_since = (datetime.now() - last_loss_time).total_seconds() / 3600
            
            if hours_since < 72:
                return {
                    "forced_hold": True,
                    "consecutive_losses": consecutive_losses,
                    "message": f"🚨 连续{consecutive_losses}次止损，强制暂停72小时（已过{hours_since:.1f}小时）"
                }
        
        elif consecutive_losses >= 3:
            # 检查是否在24小时内
            last_loss_time = recent_closed[0]['closed_at']
            hours_since = (datetime.now() - last_loss_time).total_seconds() / 3600
            
            if hours_since < 24:
                return {
                    "forced_hold": True,
                    "consecutive_losses": consecutive_losses,
                    "message": f"🚨 连续{consecutive_losses}次止损，强制暂停24小时（已过{hours_since:.1f}小时）"
                }
        
        elif consecutive_losses >= 2:
            # 检查是否在45分钟内
            last_loss_time = recent_closed[0]['closed_at']
            minutes_since = (datetime.now() - last_loss_time).total_seconds() / 60
            
            if minutes_since < 45:
                return {
                    "forced_hold": True,
                    "consecutive_losses": consecutive_losses,
                    "message": f"⚠️ 连续{consecutive_losses}次止损，需冷静45分钟（已过{minutes_since:.1f}分钟）"
                }
        
        return {
            "forced_hold": False,
            "consecutive_losses": consecutive_losses,
            "message": ""
        }

    def get_20_position_info(self,trader_id:str):
        recent_positions = self.db.execute("""
        SELECT * FROM positions
        WHERE trader_id = %s
        AND status = 'closed'
        ORDER BY opened_at DESC
        LIMIT 20
        """,(trader_id,))
        if not recent_positions:
            return None
        position_info = {}
        for position in recent_positions:
            position_info[position["symbol"]] = {
                "entry_price": position["entry_price"],
                "quantity": position["quantity"],
            }
        return recent_positions