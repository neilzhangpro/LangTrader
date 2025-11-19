# 修改 src/LangTrader/ai/prompt.py

from typing import Dict, Any, List
from src.LangTrader.utils import logger

class PromptTemplate:
    """提示词模板系统 - 支持分层和自定义"""
    
    # 默认模板结构（用户可覆盖）- 持仓和历史表现前置
    DEFAULT_TEMPLATE = """
{critical_alerts}

=== 📊 当前持仓状态 ===
{position_data}
{position_guide}

=== 📊 实时性能监控 ===
{performance_signal}

=== 📈 历史表现 ===
{historical_performance}
{trading_guidance}

=== 🧠 历史反馈学习 ===
{feedback_instructions}

=== 🚨 交易纪律控制 ===
{frequency_control}

=== 📊 市场分析 ===
{market_data}
{signal_strength}
{sentiment_section}
{news_section}

=== 🛡️ 风控规则 ===
{risk_rules}

=== 🎯 交易任务 ===
{task_instructions}
"""
    
    def __init__(self, custom_template: str = None):
        """
        初始化提示词模板
        
        Args:
            custom_template: 用户自定义模板（支持变量替换）
        """
        self.template = custom_template or self.DEFAULT_TEMPLATE
    
    def build_prompt(self, params: Dict[str, Any]) -> str:
        """
        构建最终提示词
        
        Args:
            params: 统一的参数字典，包含所有模板变量
            
        Returns:
            格式化后的提示词
        """
        try:
            return self.template.format(**params)
        except KeyError as e:
            logger.error(f"❌ 模板变量缺失: {e}")
            logger.error(f"可用变量: {list(params.keys())}")
            raise


class Prompt:
    """提示词生成器 - 优化版（保留完整信息）"""
    
    def __init__(self, custom_template: str = None, historical_performance_module=None):
        self.template_engine = PromptTemplate(custom_template)
        self.historical_performance_module = historical_performance_module
    
    def get_user_prompt(self, state: Dict, config, coin_list: List[str]) -> str:
        """
        动态生成用户提示词
        
        核心改进：
        1. 统一参数字典（支持自定义）
        2. 分层清晰（持仓+历史前置）
        3. 保留完整数据（不简化）
        4. 减少冗余说明
        """
        # 构建统一参数字典
        params = self._build_unified_params(state, config, coin_list)
        
        # 使用模板引擎生成
        user_prompt = self.template_engine.build_prompt(params)
        
        logger.debug(f"📝 提示词生成完成，长度: {len(user_prompt)} 字符")
        return user_prompt
    
    def _build_unified_params(self, state: Dict, config, coin_list: List[str]) -> Dict[str, Any]:
        """
        构建统一的参数字典
        
        所有模板变量集中管理，方便用户自定义模板
        """
        # 提取基础数据
        win_rate = state["historical_performance"].get("win_rate", 0)
        total_trades = state["historical_performance"].get("total_positions", 0)
        winning = state["historical_performance"].get("winning_positions", 0)
        losing = state["historical_performance"].get("losing_positions", 0)
        recent_decisions = state["historical_performance"].get("recent_decisions", "暂无历史")
        risk_cfg = config.risk_config
        
        # === 构建各部分内容 ===
        
        # 1. 关键预警（如果有紧急情况放最前）
        critical_alerts = self._format_critical_alerts(state, risk_cfg)
        
        # 2. 持仓数据（简要文本）
        position_data = state.get("position_data", "当前无持仓")
        
        # 3. 持仓指导（详细操作建议）
        position_guide = self._get_position_action_guide(state, risk_cfg)
        
        # 4. 历史表现
        historical_performance = self._format_historical_performance(
            total_trades, winning, losing, win_rate, recent_decisions
        )
        
        # 5. 交易指导（根据胜率动态调整）
        trading_guidance = self._get_trading_guidance(win_rate, total_trades)
        
        # 6. 🆕 反馈使用指令（核心新增）
        feedback_instructions = ""
        if self.historical_performance_module:
            feedback_instructions = self._format_feedback_instructions(
                state.get("coin_performance", {}),
                win_rate,
                state.get("trader_id", ""),
                self.historical_performance_module
            )
        
        # 6.1 🆕 交易频率控制
        frequency_control = ""
        if self.historical_performance_module:
            freq_check = self.historical_performance_module.check_trading_frequency(
                state.get("trader_id", "")
            )
            frequency_control = self._format_frequency_control(freq_check)
        
        # 6.2 🆕 连续止损检查
        stop_loss_check = ""
        if self.historical_performance_module:
            sl_check = self.historical_performance_module.check_consecutive_stop_loss(
                state.get("trader_id", "")
            )
            stop_loss_check = self._format_stop_loss_check(sl_check)
        
        # 合并频率控制和止损检查
        frequency_control = frequency_control + "\n" + stop_loss_check
        
        # 7. 市场数据（完整保留）
        market_data = state.get("market_data", "市场数据加载中...")
        
        # 8. 信号强度分析
        signal_strength = self._analyze_signal_strength(market_data)
        
        # 9. 情绪数据（完整保留）
        sentiment_section = self._format_sentiment_data(state.get("sentiment_data", {}))
        
        # 10. 新闻（完整保留）
        news_section = self._format_global_news(state.get("global_news", []))
        
        # 11. 风控规则
        risk_rules = self._format_risk_rules(risk_cfg)
        
        # 12. 任务说明
        task_instructions = self._format_task_instructions(coin_list, risk_cfg)
        performance_signal = state.get("performance_signal", "")
        
        # 13. BTC优先检查（暂时为空，待实现）
        btc_priority_check = ""
        
        # === 返回完整参数字典 ===
        return {
            # 🆕 模板组件（预格式化，按重要性排序）
            "critical_alerts": critical_alerts,
            "position_data": position_data,
            "position_guide": position_guide,
            "historical_performance": historical_performance,
            "trading_guidance": trading_guidance,
            "feedback_instructions": feedback_instructions,
            "frequency_control": frequency_control,  # 🆕 交易频率控制
            "btc_priority_check": btc_priority_check,  # 🆕 BTC优先检查（暂时为空）
            "market_data": market_data,
            "signal_strength": signal_strength,
            "sentiment_section": sentiment_section,
            "news_section": news_section,
            "risk_rules": risk_rules,
            "task_instructions": task_instructions,
            
            # 🆕 智能指导（如果有）
            "smart_guidance": state.get("smart_guidance", ""),
            "coin_performance": state.get("coin_performance", {}),
            
            # 🆕 配置参数（用于自定义模板）
            "coins": ", ".join(coin_list),
            "coin_list": coin_list,
            "win_rate": win_rate,
            "win_rate_pct": f"{win_rate:.1%}",
            "total_trades": total_trades,
            "winning_trades": winning,
            "losing_trades": losing,
            "max_leverage": risk_cfg.get("max_leverage", 5),
            "stop_loss_pct": risk_cfg.get("stop_loss_percent", 0.05) * 100,
            "take_profit_pct": risk_cfg.get("take_profit_percent", 0.12) * 100,
            "max_position_pct": risk_cfg.get("max_position_size", 0.25) * 100,
            "performance_signal": performance_signal,
        }
    
    def _format_critical_alerts(self, state: Dict, risk_cfg: dict) -> str:
        """关键预警（仅在有紧急情况时显示）"""
        current_positions = state.get("current_positions", {})
        if not current_positions:
            return ""
        
        stop_loss_pct = risk_cfg.get("stop_loss_percent", 0.05) * 100
        take_profit_pct = risk_cfg.get("take_profit_percent", 0.12) * 100
        
        alerts = []
        for symbol, pos in current_positions.items():
            pnl = pos.get("pnl_percentage", 0)
            side = pos.get("side", "")
            
            # 触发止损警告
            if pnl <= -stop_loss_pct * 0.8:  # 80%止损线
                alerts.append(
                    f"🚨 {symbol} {side.upper()} 浮亏{pnl:+.2f}% "
                    f"(已接近止损线-{stop_loss_pct:.0f}%，必须关注！)"
                )
            # 达到止盈提醒
            elif pnl >= take_profit_pct * 0.8:  # 80%止盈线
                alerts.append(
                    f"💰 {symbol} {side.upper()} 盈利{pnl:+.2f}% "
                    f"(接近止盈目标+{take_profit_pct:.0f}%，可考虑止盈)"
                )
        
        if alerts:
            return "=== ⚠️ 紧急关注 ===\n" + "\n".join(alerts) + "\n"
        return ""
    
    def _analyze_signal_strength(self, market_data: str) -> str:
        """信号强度分析（保留完整）"""
        if not market_data:
            return ""
        
        buy_signals = market_data.lower().count('buy') + market_data.lower().count('买入')
        sell_signals = market_data.lower().count('sell') + market_data.lower().count('卖出')
        hold_signals = market_data.lower().count('hold') + market_data.lower().count('观望')
        
        total_signals = buy_signals + sell_signals + hold_signals
        if total_signals == 0:
            return ""
        
        buy_pct = buy_signals / total_signals
        sell_pct = sell_signals / total_signals
        hold_pct = hold_signals / total_signals
        
        # 判断信号明确度
        max_signal = max(buy_pct, sell_pct)
        if max_signal > 0.6:
            clarity = "高"
            clarity_desc = "多数策略一致"
            clarity_emoji = "✅✅"
        elif max_signal > 0.45:
            clarity = "中"
            clarity_desc = "策略略有分歧"
            clarity_emoji = "✅"
        else:
            clarity = "低"
            clarity_desc = "策略严重分歧"
            clarity_emoji = "⚠️"
        
        dominant_signal = "看多" if buy_pct > sell_pct else "看空" if sell_pct > buy_pct else "中性"
        
        return f"""
=== 🎯 信号强度分析 ===
📊 看多信号: {buy_pct:.0%} ({buy_signals}个)
📊 看空信号: {sell_pct:.0%} ({sell_signals}个)
📊 观望信号: {hold_pct:.0%} ({hold_signals}个)

**综合判断：** {dominant_signal}倾向明显
**信号明确度：** {clarity} - {clarity_desc} {clarity_emoji}
"""
    
    def _format_sentiment_data(self, sentiment_data: dict) -> str:
        """格式化情绪数据（完整保留）"""
        if not sentiment_data:
            return ""
        
        sections = ["\n=== 📊 市场情绪指标 ===\n"]
        
        for symbol, data in sentiment_data.items():
            if not data:
                continue
            
            sections.append(f"【{symbol}】")
            
            # 恐慌贪婪指数
            fng = data.get("fear_greed_index", {})
            if fng:
                sections.append(
                    f"🎭 恐慌贪婪指数: {fng['value']}/100 ({fng['classification']}) - {fng['interpretation']}"
                )
            
            # 资金费率
            funding = data.get("funding_rate", {})
            if funding and funding.get("rate") != 0:
                sections.append(
                    f"💰 资金费率: {funding['rate']:.4%} - {funding['interpretation']}"
                )
            
            sections.append("")  # 空行
        
        sections.append("""💡 **情绪指标使用建议：**
- 恐慌指数<25 + 技术超卖 → 可能是抄底机会
- 贪婪指数>75 + 技术超买 → 警惕顶部风险
- 资金费率极端值 → 可能出现反向运动
""")
        
        return "\n".join(sections)
    
    def _format_global_news(self, news_list: list) -> str:
        """格式化全局新闻（完整保留）"""
        if not news_list:
            logger.debug("📰 无全局新闻")
            return ""
        
        logger.debug(f"📰 格式化 {len(news_list)} 条新闻")
        
        sections = ["\n=== 📰 市场新闻动态 ===\n"]
        
        for i, item in enumerate(news_list, 1):
            title = item.get('title', '')[:80]
            source = item.get('source', 'Unknown')
            sections.append(f"{i}. [{source}] {title}...")
        
        sections.append("""
💡 **新闻使用建议：**
- 重大负面新闻（监管、黑客、崩盘） → 优先规避风险
- 重大利好新闻（ETF通过、机构入场） → 可放大仓位
- 普通新闻 → 作为辅助参考
""")
        
        return "\n".join(sections)
    
    def _format_risk_rules(self, risk_config: dict) -> str:
        """格式化风控规则（简化冗余说明）"""
        stop_loss_pct = risk_config.get("stop_loss_percent", 0.05) * 100
        take_profit_pct = risk_config.get("take_profit_percent", 0.12) * 100
        max_leverage = risk_config.get("max_leverage", 5)
        max_position = risk_config.get("max_position_size", 0.25) * 100
        risk_reward_ratio = take_profit_pct / stop_loss_pct
        
        return f"""
账户风险参数：
- 最大杠杆: {max_leverage}倍
- 最大仓位: {max_position:.0f}%
- 止损线: -{stop_loss_pct:.0f}%（触发自动平仓）
- 止盈目标: +{take_profit_pct:.0f}%
- 目标盈亏比: {risk_reward_ratio:.1f}:1

强制规则：
1. 亏损达-{stop_loss_pct:.0f}% → 必须平仓
2. 盈利达+{take_profit_pct:.0f}% → 建议止盈
3. 杠杆 ≤ {max_leverage}倍
4. 单仓位 ≤ {max_position:.0f}%
"""
    
    def _format_historical_performance(
        self, total: int, winning: int, losing: int, win_rate: float, recent_decisions: str
    ) -> str:
        """格式化历史表现（完整保留）"""
        return f"""
近期交易记录：
- 总交易: {total}笔
- 盈利: {winning}笔
- 亏损: {losing}笔
- 胜率: {win_rate:.1%}

最近3次决策回顾：
{recent_decisions}
"""
    
    def _get_trading_guidance(self, win_rate: float, total_trades: int) -> str:
        """动态交易指导（保留完整）"""
        if total_trades < 5:
            return """
=== 📊 当前阶段：初期建仓 ===
策略建议：
✅ 积极寻找机会建立交易记录
✅ 信号强度>50%即可尝试（小仓位）
✅ 严格执行止损
✅ 每次交易都是学习机会
"""
        
        if win_rate < 0.40:
            return f"""
=== 📊 当前阶段：调整优化期（胜率{win_rate:.1%}） ===
策略建议：
✅ 提高交易门槛：信号强度>65%
✅ 避开信号明确度"低"的标的
✅ 优先选择趋势明显的市场
✅ 杠杆控制在1-2倍
✅ 快进快出，不恋战

注意：不要因胜率低就不敢交易，用止损管理风险即可
"""
        
        elif win_rate < 0.50:
            return f"""
=== 📊 当前阶段：稳健交易期（胜率{win_rate:.1%}） ===
策略建议：
✅ 信号强度>55%可考虑
✅ 优先选择信号明确度"高"的机会
✅ 提高盈亏比：让盈利仓位多跑
✅ 快速止损：亏损仓位快跑
✅ 分析失败交易，避免重复错误
"""
        
        else:
            return f"""
=== 📊 当前阶段：优势保持期（胜率{win_rate:.1%}） ===
策略建议：
✅ 信号强度>45%即可建仓
✅ 可适度使用2-3倍杠杆（高置信度时）
✅ 盈利>5%考虑加仓
✅ 延续有效的交易模式
✅ 继续严格止损

警惕：不要因连胜而过度自信
"""
    
    def _format_feedback_instructions(
        self, 
        coin_performance: dict, 
        win_rate: float, 
        trader_id: str,
        historical_performance_module
    ) -> str:
        """
        🆕 生成反馈使用指令（告诉AI如何使用历史数据）
        """
        if not coin_performance:
            return ""
        
        instructions = ["\n=== 🧠 历史反馈学习（必读）===\n"]
        
        # 1. 连续亏损币种处理（硬性规则）
        danger_coins = [
            symbol for symbol, data in coin_performance.items()
            if data.get('consecutive_losses', 0) >= 3
        ]
        
        if danger_coins:
            instructions.append("**🚫 禁止交易规则（强制执行）：**")
            for symbol in danger_coins:
                data = coin_performance[symbol]
                instructions.append(
                    f"- {symbol}：连续{data['consecutive_losses']}次止损，"
                    f"**本次决策严禁选择该币种**（需等待至少2次其他成功交易后才可重新考虑）"
                )
            instructions.append("")
        
        # 2. 优势币种强化
        excellent_coins = [
            (symbol, data) for symbol, data in coin_performance.items()
            if data.get('win_rate', 0) >= 0.7 and data.get('total_trades', 0) >= 3
        ]
        
        if excellent_coins:
            instructions.append("**✅ 优先选择规则：**")
            for symbol, data in excellent_coins:
                instructions.append(
                    f"- {symbol}：胜率{data['win_rate']:.0%}，"
                    f"平均盈利{data.get('avg_profit_pct', 0):+.1f}%，"
                    f"**如果技术信号强度>50%，优先选择该币种**"
                )
            instructions.append("")
        
        # 3. 失败模式识别（从亏损中学习）
        instructions.append("**📉 失败模式识别（避免重蹈覆辙）：**")
        
        try:
            recent_losses = historical_performance_module.analyze_recent_losses(trader_id)
            if recent_losses:
                for pattern in recent_losses:
                    instructions.append(f"- {pattern}")
            else:
                instructions.append("- 暂无明显失败模式")
        except Exception as e:
            logger.error(f"分析失败模式出错: {e}")
            instructions.append("- 暂无失败模式数据")
        
        instructions.append("")
        
        # 4. 成功模式强化（从盈利中学习）
        instructions.append("**📈 成功模式强化（复制成功经验）：**")
        
        try:
            recent_wins = historical_performance_module.analyze_recent_wins(trader_id)
            if recent_wins:
                for pattern in recent_wins:
                    instructions.append(f"- {pattern}")
            else:
                instructions.append("- 暂无明显成功模式")
        except Exception as e:
            logger.error(f"分析成功模式出错: {e}")
            instructions.append("- 暂无成功模式数据")
        
        instructions.append("")
        
        # 5. 整体策略调整（基于胜率动态调整）
        instructions.append("**🎯 本次决策要求（基于历史表现）：**")
        
        if win_rate < 0.4:
            instructions.append(
                "由于整体胜率低于40%，本次决策必须满足："
                "\n  1. ✅ 信号明确度必须为'高'（多数策略一致>60%）"
                "\n  2. ✅ 避开所有连续亏损币种"
                "\n  3. ✅ 置信度必须>0.7"
                "\n  4. ✅ 杠杆不超过2倍"
                "\n  5. ⚠️ 如果没有符合条件的机会，输出HOLD"
            )
        elif win_rate < 0.5:
            instructions.append(
                "由于胜率接近50%，本次决策建议："
                "\n  1. 信号明确度'中'或'高'（>50%）"
                "\n  2. 避开连续亏损3次以上的币种"
                "\n  3. 置信度>0.6"
                "\n  4. 杠杆2-3倍"
            )
        else:
            instructions.append(
                "由于胜率良好（>50%），本次决策可以："
                "\n  1. 信号强度>45%即可交易"
                "\n  2. 优先选择表现优异的币种"
                "\n  3. 置信度>0.5"
                "\n  4. 杠杆可用3-5倍（高置信度时）"
                "\n  5. 盈利仓位可适当延长持有"
            )
        
        instructions.append("")
        instructions.append("**💡 决策原则：**")
        instructions.append("- 历史表现是重要参考，但不是绝对依据")
        instructions.append("- 结合当前市场信号和历史反馈做综合判断")
        instructions.append("- 连续亏损的币种必须避开，这是硬性规则")
        
        return "\n".join(instructions)
    
    def _format_frequency_control(self, freq_check: dict) -> str:
        """格式化交易频率控制信息"""
        if not freq_check:
            return ""
        
        message = freq_check.get('message', '')
        if not message:
            return ""
        
        if freq_check.get('forced_hold'):
            return f"\n{message}\n**本次必须 HOLD，不得开仓！**\n"
        else:
            return f"\n{message}\n"
    
    def _format_stop_loss_check(self, sl_check: dict) -> str:
        """格式化连续止损检查信息"""
        if not sl_check:
            return ""
        
        message = sl_check.get('message', '')
        if not message:
            return ""
        
        if sl_check.get('forced_hold'):
            return f"\n{message}\n**强制暂停期间，本次必须 HOLD！**\n"
        else:
            consecutive = sl_check.get('consecutive_losses', 0)
            if consecutive > 0:
                return f"\n💡 提示：之前有{consecutive}次连续止损，请谨慎交易\n"
            return ""
    
    def _get_position_action_guide(self, state: Dict, risk_config: dict) -> str:
        """持仓操作指导（完整保留）"""
        current_positions = state.get("current_positions", {})
        
        if not current_positions:
            return ""
        
        stop_loss_pct = risk_config.get("stop_loss_percent", 0.05) * 100
        take_profit_pct = risk_config.get("take_profit_percent", 0.12) * 100
        
        guides = ["\n=== ⚠️ 当前持仓操作指导 ===\n"]
        
        for symbol, pos in current_positions.items():
            side = pos.get("side", "")
            pnl_pct = pos.get("pnl_percentage", 0)
            entry_price = pos.get("entry_price", 0)
            current_price = pos.get("current_price", 0)
            
            # 计算止损价和止盈价
            if side == "long":
                stop_loss_price = entry_price * (1 - stop_loss_pct/100)
                take_profit_price = entry_price * (1 + take_profit_pct/100)
            else:  # short
                stop_loss_price = entry_price * (1 + stop_loss_pct/100)
                take_profit_price = entry_price * (1 - take_profit_pct/100)
            
            # 判断状态
            if pnl_pct <= -stop_loss_pct:
                status = "🚨 已触发止损线！"
                action = f"SELL + {side}"
                urgency = "⚠️ 必须立即平仓！"
                color = "红色预警"
            elif pnl_pct >= take_profit_pct:
                status = "✅ 已达止盈目标！"
                action = f"SELL + {side} 或 HOLD（移动止损）"
                urgency = "💰 建议止盈锁定利润"
                color = "绿色达标"
            elif pnl_pct <= -stop_loss_pct * 0.7:
                status = f"⚠️ 接近止损线（浮亏{abs(pnl_pct):.2f}%）"
                action = f"根据趋势判断：SELL + {side} 或 HOLD"
                urgency = f"📉 距离止损还有{abs(pnl_pct + stop_loss_pct):.2f}%"
                color = "黄色预警"
            elif pnl_pct < 0:
                status = f"📊 当前浮亏 {pnl_pct:+.2f}%"
                action = f"根据趋势判断"
                urgency = f"⏳ 距止损{abs(pnl_pct + stop_loss_pct):.2f}%"
                color = "观察状态"
            elif pnl_pct >= take_profit_pct * 0.7:
                status = f"📈 接近止盈（盈利{pnl_pct:.2f}%）"
                action = f"SELL + {side}（部分）或 HOLD"
                urgency = f"💡 距止盈{take_profit_pct - pnl_pct:.2f}%"
                color = "盈利状态"
            else:
                status = f"📈 盈利 {pnl_pct:+.2f}%"
                action = "HOLD 或根据趋势调整"
                urgency = f"💡 距止盈{take_profit_pct - pnl_pct:.2f}%"
                color = "盈利状态"
            
            guides.append(f"""
【{symbol}】({color})
方向: {side.upper()} | 入场: ${entry_price:,.4f} | 当前: ${current_price:,.4f}
盈亏: {pnl_pct:+.2f}% | 止损: ${stop_loss_price:,.4f} | 止盈: ${take_profit_price:,.4f}
{status}
→ 建议: {action}
→ {urgency}
""")
        
        guides.append("""
🔔 **平仓指令语法提醒：**
- 持有long仓平仓 → 输出 "SELL + long"
- 持有short仓平仓 → 输出 "SELL + short"
- ❌ 绝不能输出 "SELL + none"（这是无效指令）
""")
        
        return "\n".join(guides)
    
    def _format_task_instructions(self, coin_list: List[str], risk_cfg: dict) -> str:
        """任务说明（增强版，包含疑惑优先原则）"""
        max_leverage = risk_cfg.get("max_leverage", 5)
        stop_loss = risk_cfg.get("stop_loss_percent", 0.05) * 100
        take_profit = risk_cfg.get("take_profit_percent", 0.12) * 100
        
        return f"""
基于以上信息，做出交易决策：

⚠️ **零号原则：疑惑优先（最高优先级）**
- 当你不确定时，默认选择 HOLD
- 完全确定（置信度≥85%且无任何犹豫）→ 才开仓
- 不确定是否符合条件 = 视为不符合 → HOLD
- 宁可错过机会，不做模糊决策

**开仓前自检（任一回答"否" → HOLD）：**
1. 我是否100%确定这是高质量机会？
2. 信号强度是否≥70%？
3. 我能清楚说出3个开仓理由吗？
4. 我是否因为"太久没交易"而急于开仓？

**可交易币种：** {', '.join(coin_list)}

**决策格式：**
- 开仓: BUY + long（看涨）或 BUY + short（看跌）
- 平仓: SELL + long/short（side必须与持仓一致）
- 观望: HOLD + none

**参数设置：**
- 置信度要求: 
  * <0.75: 不要交易，选择 HOLD
  * 0.75-0.85: 可交易，杠杆{max_leverage//2}倍
  * >0.85: 高质量机会，杠杆{max_leverage}倍
- 杠杆: 严格 1-{max_leverage}倍

**分析说明：**
- 开仓时: 说明入场逻辑、预期止损(-{stop_loss:.0f}%)、止盈(+{take_profit:.0f}%)
- 平仓时: 说明平仓原因（止损/止盈/趋势反转/信号变化）
- 持有时: 说明为什么继续持有

**核心原则：**
- 质量优于数量（宁可错过，不做低质量交易）
- 疑惑时选择 HOLD
- 让利润奔跑，快速止损
- 小亏多次 < 大亏一次（保护本金）
"""


# 🆕 自定义模板示例
# 用户可以通过配置数据库或API设置自己的模板

MINIMALIST_TEMPLATE = """
=== 关键信息 ===
{critical_alerts}
持仓: {position_data}
{historical_performance}

=== 市场 ===
{market_data}

=== 决策 ===
可交易: {coins}
规则: 止损{stop_loss_pct}% 止盈{take_profit_pct}% 杠杆≤{max_leverage}倍
选择最佳币种，做出BUY/SELL/HOLD决策。
"""

DETAILED_TEMPLATE = """
{critical_alerts}

=== 📊 持仓状态 ===
{position_data}
{position_guide}

=== 📈 历史表现 ===
{historical_performance}
{trading_guidance}

=== 📊 完整市场数据 ===
{market_data}
{signal_strength}

=== 📰 市场情绪 ===
{sentiment_section}
{news_section}

=== 🛡️ 风控 ===
{risk_rules}

=== 🎯 任务 ===
{task_instructions}

**币种表现分析：**
{smart_guidance}
"""
