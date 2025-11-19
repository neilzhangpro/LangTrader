"""
回测运行器 - 使用LLM做决策
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

from src.LangTrader.backtest.historical_data_fetcher import HistoricalDataFetcher
from src.LangTrader.backtest.mock_position import MockPositionManager
from src.LangTrader.backtest.performance_metrics import PerformanceAnalyzer
from src.LangTrader.config import Config
from src.LangTrader.utils import logger
from src.LangTrader.ai.prompt import Prompt
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

# 导入策略
from src.LangTrader.strategy.rsi_strategy import RSIStrategy
from src.LangTrader.strategy.macd_strategy import MACDStrategy
from src.LangTrader.strategy.ema_strategy import EMA20Strategy
from src.LangTrader.strategy.bbu_strategy import BBUStrategy
from src.LangTrader.strategy.volume_strategy import VolumeStrategy
from src.LangTrader.strategy.ichimoku_strategy import IchimokuStrategy

class TradingDecision(BaseModel):
    """LLM 结构化输出模型（复用）"""
    symbol: str = Field(description="选择的交易币种，如 BTC, ETH")
    action: str = Field(description="交易动作: BUY, SELL, 或 HOLD")
    side: str = Field(description="方向: long 或 short，如果是 HOLD 则为 none")
    confidence: float = Field(description="决策置信度，范围 0.0 到 1.0", ge=0.0, le=1.0)
    leverage: int = Field(description="建议杠杆倍数，范围 1 到 10", ge=1, le=10)
    analysis: str = Field(description="决策分析理由")

class BacktestRunner:
    """回测运行器 - 完整模拟实盘决策流程"""
    
    def __init__(
        self,
        trader_id: str,
        start_date: str,
        end_date: str,
        initial_balance: float = 10000.0,
        symbols: Optional[List[str]] = None,
        strategies: Optional[List[str]] = None,  # 要使用哪些策略信号
        custom_prompt: Optional[str] = None,     # 自定义system_prompt
        granularity: int = 14400  # 4小时K线
    ):
        # 加载配置
        self.config = Config(trader_id=trader_id)
        
        # 覆盖配置
        if symbols:
            self.config.symbols = symbols
        if custom_prompt:
            self.config.system_prompt = custom_prompt
        
        # 时间范围
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.granularity = granularity
        
        # 初始化LLM
        model_name = self.config.llm_config["openai"]["model"]
        api_key = self.config.llm_config["openai"]["api_key"]
        base_url = self.config.llm_config["openai"]["base_url"]
        self.llm = init_chat_model(model=model_name, api_key=api_key, base_url=base_url)
        self.structured_llm = self.llm.with_structured_output(TradingDecision)
        
        # 策略配置（要使用哪些策略信号）
        self.strategy_names = strategies or ["RSI", "MACD", "EMA", "BBU", "Volume", "Ichimoku"]
        self.strategies = self._load_strategies()
        
        # 初始化组件
        self.position_manager = MockPositionManager(
            initial_balance=initial_balance,
            risk_config=self.config.risk_config
        )
        
        # 数据预热：从更早的日期开始获取数据，确保技术指标有足够数据
        # 50天预热期约200根4h K线，足够计算所有技术指标
        warmup_days = 50
        data_start_date = self.start_date - timedelta(days=warmup_days)
        logger.info(f"数据预热期: {warmup_days}天，从 {data_start_date.date()} 开始获取数据")
        
        self.data_fetcher = HistoricalDataFetcher(
            symbols=self.config.symbols,
            start_date=data_start_date,  # 数据从更早开始
            end_date=self.end_date
        )
        
        self.prompt_builder = Prompt()
        
        # 决策记录（用于模拟历史表现）
        self.decision_history = []
    
    def _load_strategies(self) -> List:
        """加载策略实例"""
        strategy_map = {
            "RSI": RSIStrategy(),
            "MACD": MACDStrategy(),
            "EMA": EMA20Strategy(),
            "BBU": BBUStrategy(),
            "Volume": VolumeStrategy(),
            "Ichimoku": IchimokuStrategy()
        }
        
        strategies = []
        for name in self.strategy_names:
            if name in strategy_map:
                strategies.append(strategy_map[name])
                logger.info(f"✅ 加载策略: {name}")
            else:
                logger.warning(f"⚠️ 策略 {name} 不存在")
        
        return strategies
    
    def run(self) -> Dict:
        """运行完整回测"""
        logger.info("=" * 60)
        logger.info("🚀 开始回测（LLM决策模式）")
        logger.info(f"时间范围: {self.start_date.date()} 到 {self.end_date.date()}")
        logger.info(f"币种: {self.config.symbols}")
        logger.info(f"策略信号: {self.strategy_names}")
        logger.info(f"初始资金: ${self.position_manager.initial_balance:,.2f}")
        logger.info(f"LLM模型: {self.config.llm_config['openai']['model']}")
        logger.info("=" * 60)
        
        # 1. 获取历史数据
        logger.info("\n📊 步骤1: 获取历史数据...")
        historical_data = self.data_fetcher.fetch_all_data(self.granularity)
        
        if not historical_data:
            logger.error("❌ 未获取到任何历史数据，回测终止")
            return {"error": "未获取到历史数据"}
        
        # 2. 时间步进回测
        logger.info("\n⏳ 步骤2: 开始时间步进回测...")
        current_time = self.start_date
        step_interval = timedelta(seconds=self.granularity)
        step_count = 0
        decision_count = 0
        
        while current_time <= self.end_date:
            step_count += 1
            
            # 获取当前时间点的市场快照
            market_snapshot = self.data_fetcher.get_data_at_time(current_time)
            current_prices = self.data_fetcher.get_current_prices(current_time)
            
            if not current_prices:
                current_time += step_interval
                continue
            
            # 更新持仓（检查止损止盈）
            self.position_manager.update_positions(current_prices, current_time)
            
            # 每N个周期进行一次LLM决策（避免过于频繁，可配置）
            decision_interval = 1  # 每1个周期决策一次（4小时）
            if step_count % decision_interval == 0:
                try:
                    # 调用LLM进行决策
                    decision = self._llm_decision(market_snapshot, current_prices, current_time)
                    
                    if decision and decision['action'] != 'HOLD':
                        decision_count += 1
                        self._execute_trade(decision, current_time)
                        
                        # 记录决策历史（用于后续生成历史表现提示）
                        self.decision_history.append({
                            'symbol': decision['symbol'],
                            'action': decision['action'],
                            'side': decision['side'],
                            'confidence': decision['confidence'],
                            'analysis': decision['analysis'][:100],
                            'timestamp': current_time
                        })
                
                except Exception as e:
                    logger.error(f"❌ LLM决策失败: {e}")
            
            # 记录资金曲线
            self.position_manager.record_equity(current_prices, current_time)
            
            # 进度日志
            if step_count % 50 == 0:
                progress = (current_time - self.start_date) / (self.end_date - self.start_date)
                logger.info(
                    f"进度: {progress:.0%} | "
                    f"余额: ${self.position_manager.current_balance:,.2f} | "
                    f"决策次数: {decision_count}"
                )
            
            # 前进一个时间步
            current_time += step_interval
        
        # 3. 平掉所有持仓
        logger.info("\n📌 步骤3: 平掉所有持仓...")
        final_prices = self.data_fetcher.get_current_prices(self.end_date)
        self.position_manager.close_all_positions(final_prices, self.end_date)
        
        # 4. 计算性能指标
        logger.info("\n📈 步骤4: 计算性能指标...")
        analyzer = PerformanceAnalyzer(
            closed_positions=self.position_manager.closed_positions,
            equity_curve=self.position_manager.equity_curve,
            initial_balance=self.position_manager.initial_balance,
            final_balance=self.position_manager.current_balance
        )
        
        performance = analyzer.calculate_all_metrics()
        performance['total_decisions'] = decision_count
        
        # 5. 生成报告
        logger.info("\n" + "=" * 60)
        logger.info("✅ 回测完成！")
        self._print_summary(performance)
        logger.info("=" * 60)
        
        return {
            "config": {
                "strategies": self.strategy_names,
                "system_prompt": self.config.system_prompt[:200],
                "symbols": self.config.symbols,
                "date_range": f"{self.start_date.date()} - {self.end_date.date()}"
            },
            "performance": performance,
            "trades": [pos.to_dict() for pos in self.position_manager.closed_positions],
            "equity_curve": self.position_manager.equity_curve
        }
    
    def _llm_decision(
        self,
        market_snapshot: Dict[str, pd.DataFrame],
        current_prices: Dict[str, float],
        current_time: datetime
    ) -> Optional[Dict]:
        """
        核心：使用LLM进行决策
        完全模拟 decision_engine.py 的 _llm_analysis 流程
        """
        
        # 1. 生成市场分析（策略信号）
        market_data_text = self._generate_market_analysis(market_snapshot)
        
        # 2. 生成持仓分析
        position_data_text = self._generate_position_analysis(current_prices)
        
        # 3. 模拟历史表现（使用当前回测的历史）
        historical_performance = self._calculate_recent_performance()
        
        # 4. 构建state（模拟DecisionEngineState）
        state = {
            "trader_id": self.config.trader_id,
            "market_data": market_data_text,
            "position_data": position_data_text,
            "historical_performance": historical_performance,
            "current_positions": self._get_current_positions_dict(current_prices),
            # 回测中无法获取实时情绪数据和新闻，提供空数据
            "sentiment_data": {},
            "global_news": []
        }
        
        # 5. 使用Prompt构建用户提示词
        user_prompt = self.prompt_builder.get_user_prompt(
            state,
            self.config,
            self.config.symbols
        )
        
        # 6. 调用LLM
        messages = [
            SystemMessage(content=self.config.system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        try:
            decision = self.structured_llm.invoke(messages)
            
            logger.debug(
                f"🤖 LLM决策: {decision.action} {decision.symbol} "
                f"{decision.side} @ {decision.confidence:.2f}"
            )
            
            return {
                'symbol': decision.symbol,
                'action': decision.action,
                'side': decision.side,
                'confidence': decision.confidence,
                'leverage': decision.leverage,
                'analysis': decision.analysis,
                'price': current_prices.get(decision.symbol)
            }
        
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return None
    
    def _generate_market_analysis(self, market_snapshot: Dict[str, pd.DataFrame]) -> str:
        """
        生成市场分析文本（类似market.py的get_simple_trade_signal）
        包含所有策略信号
        """
        logger.debug(f"市场快照包含 {len(market_snapshot)} 个币种")
        
        analysis_parts = []
        
        for symbol, df in market_snapshot.items():
            logger.debug(f"  {symbol}: {len(df)} 条数据")
            
            if len(df) < 50:
                logger.warning(f"  {symbol} 数据不足50条（实际{len(df)}条），跳过市场分析")
                continue
            
            last_row = df.iloc[-1]
            
            # 🔧 确保取到标量值，避免 Series.__format__ 错误
            def safe_get(key, default=0):
                """安全获取标量值"""
                val = last_row.get(key, default)
                # 如果是 Series，取第一个值
                if isinstance(val, pd.Series):
                    return float(val.iloc[0]) if len(val) > 0 else default
                # 如果是 numpy 类型，转换为 Python 类型
                if hasattr(val, 'item'):
                    return float(val.item()) if not pd.isna(val) else default
                return float(val) if not pd.isna(val) else default
            
            # 基础信息
            symbol_info = f"""
=== {symbol} 市场分析 ===
当前价格: ${safe_get('close'):,.2f}
24H最高: ${safe_get('high'):,.2f}
24H最低: ${safe_get('low'):,.2f}
24H成交量: {safe_get('volume'):,.2f}

【关键指标】
- RSI(14): {safe_get('RSI_14'):.1f} {'(超买)' if safe_get('RSI_14', 50) > 70 else '(超卖)' if safe_get('RSI_14', 50) < 30 else '(中性)'}
- MACD: {'金叉' if safe_get('MACD_12_26_9', 0) > safe_get('MACDs_12_26_9', 0) else '死叉'}
- 布林带: {'上轨外' if safe_get('close') > safe_get('BBU_20_2.0_2.0', 999999) else '下轨外' if safe_get('close') < safe_get('BBL_20_2.0_2.0', 0) else '轨道内'}
- 均线趋势: {'多头' if safe_get('close') > safe_get('SMA_20', 0) else '空头'}

【策略信号】"""
            
            # 运行所有选定的策略
            for strategy in self.strategies:
                try:
                    signal = strategy.generate_signal(symbol, df)
                    symbol_info += f"\n• {strategy.name}: {signal.strip()}"
                except Exception as e:
                    logger.error(f"策略 {strategy.name} 失败: {e}")
            
            analysis_parts.append(symbol_info)
        
        result = "\n\n".join(analysis_parts)
        logger.debug(f"市场分析生成完成，总长度: {len(result)} 字符，包含 {len(analysis_parts)} 个币种分析")
        return result
    
    def _generate_position_analysis(self, current_prices: Dict[str, float]) -> str:
        """生成持仓分析文本"""
        if not self.position_manager.open_positions:
            return "当前无持仓"
        
        position_texts = []
        
        for symbol, position in self.position_manager.open_positions.items():
            pos_info = self.position_manager.get_position_info(symbol, current_prices)
            
            position_texts.append(f"""
【{symbol}】持仓详情
方向: {pos_info['side'].upper()}
入场价: ${pos_info['entry_price']:,.4f}
当前价: ${pos_info['current_price']:,.4f}
数量: {pos_info['quantity']:.4f}
杠杆: {pos_info['leverage']}x
浮动盈亏: ${pos_info['pnl']:+,.2f} ({pos_info['pnl_percentage']:+.2%})
止损价: ${pos_info['stop_loss_price']:,.4f}
止盈价: ${pos_info['take_profit_price']:,.4f}
""")
        
        return "\n".join(position_texts)
    
    def _calculate_recent_performance(self) -> Dict:
        """计算最近的回测表现（模拟historical_performance）"""
        closed = self.position_manager.closed_positions
        
        # 取最近20笔
        recent_positions = closed[-20:] if len(closed) > 20 else closed
        
        if not recent_positions:
            return {
                "total_positions": 0,
                "winning_positions": 0,
                "losing_positions": 0,
                "win_rate": 0.0,
                "recent_decisions": "暂无历史交易"
            }
        
        winning = len([p for p in recent_positions if p.realized_pnl > 0])
        losing = len([p for p in recent_positions if p.realized_pnl < 0])
        total = len(recent_positions)
        
        # 生成最近决策摘要
        recent_text = ""
        for i, pos in enumerate(recent_positions[-3:], 1):
            recent_text += f"\n{i}. {pos.symbol} {pos.side.upper()}: PnL {pos.realized_pnl:+.2f} ({pos.pnl_percent:+.2%})"
        
        return {
            "total_positions": total,
            "winning_positions": winning,
            "losing_positions": losing,
            "win_rate": winning / total if total > 0 else 0,
            "recent_decisions": recent_text
        }
    
    def _get_current_positions_dict(self, current_prices: Dict[str, float]) -> Dict:
        """获取当前持仓字典（用于prompt）"""
        positions = {}
        
        for symbol, position in self.position_manager.open_positions.items():
            positions[symbol] = self.position_manager.get_position_info(symbol, current_prices)
        
        return positions
    
    def _execute_trade(self, decision: Dict, current_time: datetime):
        """执行交易"""
        action = decision['action']
        symbol = decision['symbol']
        price = decision.get('price')
        
        if not price:
            logger.warning(f"无法获取{symbol}价格，跳过交易")
            return
        
        if action == 'BUY':
            # 开仓
            self.position_manager.open_position(
                symbol=symbol,
                side=decision['side'],
                entry_price=price,
                leverage=decision.get('leverage', 1),
                opened_at=current_time,
                strategy_name=None  # 由LLM决策，不记录单一策略
            )
        
        elif action == 'SELL':
            # 平仓
            self.position_manager.close_position(
                symbol=symbol,
                exit_price=price,
                exit_reason='llm_decision',
                closed_at=current_time
            )
    
    def _print_summary(self, performance: Dict):
        """打印回测摘要"""
        print(f"\n{'='*60}")
        print("📊 回测结果摘要")
        print(f"{'='*60}")
        print(f"策略组合: {', '.join(self.strategy_names)}")
        print(f"LLM决策次数: {performance.get('total_decisions', 0)}")
        print(f"\n资金变化:")
        print(f"  初始资金: ${performance['initial_balance']:,.2f}")
        print(f"  最终资金: ${performance['final_balance']:,.2f}")
        print(f"  总收益: ${performance['total_pnl']:+,.2f} ({performance['total_return']:+.2%})")
        print(f"\n交易统计:")
        print(f"  总交易数: {performance['total_trades']}")
        print(f"  胜率: {performance['win_rate']:.2%}")
        print(f"  盈利交易: {performance['winning_trades']} 笔")
        print(f"  亏损交易: {performance['losing_trades']} 笔")
        print(f"\n盈亏分析:")
        print(f"  平均盈利: ${performance['avg_win']:,.2f}")
        print(f"  平均亏损: ${performance['avg_loss']:,.2f}")
        print(f"  盈亏比: {performance['profit_factor']:.2f}")
        print(f"\n风险指标:")
        print(f"  最大回撤: {performance['max_drawdown']:.2%}")
        print(f"  夏普率: {performance['sharpe_ratio']:.2f}")
        print(f"{'='*60}\n")