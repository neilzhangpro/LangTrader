# packages/langtrader_core/backtest/engine.py
"""
回测引擎 - 在历史数据上重放工作流
"""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlmodel import Session
from langtrader_core.data.models.bot import Bot
from langtrader_core.plugins.workflow import WorkflowBuilder
from langtrader_core.plugins.registry import PluginContext
from langtrader_core.graph.state import State
from langtrader_core.backtest.mock_trader import MockTrader, ExchangeBacktestDataSource
from langtrader_core.backtest.mock_performance import MockPerformanceService
from langtrader_core.services.container import ServiceContainer
from langtrader_core.services.config_manager import BotConfig
from langtrader_core.data.repositories.trade_history import TradeHistoryRepository
from langtrader_core.utils import get_logger

logger = get_logger("backtest_engine")


class BacktestEngine:
    """
    回测引擎
    
    核心思想：
    1. 用 MockTrader 替换真实 Trader
    2. 从历史数据源获取K线
    3. 复用所有现有节点（零修改）
    4. 利用 Checkpoint 保存每个周期
    """
    
    def __init__(
        self,
        bot_id: int,
        start_date: datetime,
        end_date: datetime,
        initial_balance: float = 10000,
        symbols: Optional[List[str]] = None,
        max_cycles: Optional[int] = None  # 限制最大周期数（用于快速测试）
    ):
        self.bot_id = bot_id
        self.start_date = start_date
        self.end_date = end_date
        self.initial_balance = initial_balance
        self.target_symbols = symbols
        self.max_cycles = max_cycles
        
        self.current_cycle = 0
        self.total_cycles = 0
        
        # 服务容器将在 initialize 中创建
        self.container = None
        self.cache = None
        self.rate_limiter = None
        self.bot_config_wrapper = None
    
    async def initialize(self, session: Session):
        """初始化回测环境"""
        logger.info("="*60)
        logger.info("🧪 Initializing Backtest Engine")
        logger.info("="*60)
        logger.info(f"Bot ID: {self.bot_id}")
        logger.info(f"Period: {self.start_date} → {self.end_date}")
        logger.info(f"Initial Balance: ${self.initial_balance}")
        
        # 0. 初始化服务容器
        self.container = ServiceContainer.get_instance(session)
        self.cache = self.container.get_cache()
        self.rate_limiter = self.container.get_rate_limiter()
        
        # 1. 加载 Bot 配置
        builder = WorkflowBuilder(session, self.bot_id)
        self.bot_config = builder.load_bot_config()
        
        # 加载 Bot 模型（用于 BotConfig）
        bot_model = session.get(Bot, self.bot_id)
        self.bot_config_wrapper = BotConfig(bot_model)
        logger.info(f"✅ Bot Config: timeframes={self.bot_config_wrapper.timeframes}")
        
        # 2. 创建真实交易所实例（用于拉取历史数据）
        logger.info(f"Connecting to {self.bot_config['exchange']['name']}...")
        
        exchange_cfg = self.bot_config['exchange']
        # 使用 'type' 字段获取 CCXT 交易所类型，'name' 是用户定义的显示名称
        exchange_name = exchange_cfg.get('type', exchange_cfg['name']).lower()
        
        import ccxt.pro as ccxtpro
        exchange_class = getattr(ccxtpro, exchange_name)
        exchange = exchange_class({
            'apiKey': exchange_cfg.get('apikey', ''),
            'secret': exchange_cfg.get('secretkey', ''),
            'testnet': exchange_cfg.get('testnet', True),
            'enableRateLimit': True,
        })
        
        await exchange.load_markets()
        logger.info(f"✅ Connected to {exchange_name} ({len(exchange.markets)} markets)")
        
        # 设置限流
        self.rate_limiter.set_rate_limit(exchange.rateLimit)
        
        # 3. 创建数据源
        self.data_source = ExchangeBacktestDataSource(
            self.start_date,
            self.end_date,
            exchange,
            cache=self.cache,
            rate_limiter=self.rate_limiter
        )
        
        # 4. 预加载数据
        symbols = self.target_symbols or self._get_default_symbols(exchange)
        logger.info(f"Target symbols: {symbols}")
        
        # 🔧 扩展预加载时间，确保 EMA 200 (4h) 有足够数据
        # EMA 200 在 4h 周期需要约 200*4=800 小时 ≈ 35 天
        preload_start = self.start_date - timedelta(days=35)
        await self.data_source.preload_data(symbols, ['3m', '4h'], since=preload_start)
        
        # 🔧 保存预加载的 symbols 供后续使用
        self.preloaded_symbols = symbols
        
        # 5. 创建 MockPerformanceService（纯内存，不依赖数据库）
        self.mock_performance = MockPerformanceService()
        
        # 6. 创建 MockTrader
        self.mock_trader = MockTrader(
            initial_balance=self.initial_balance,
            data_source=self.data_source,
            performance_service=self.mock_performance  # 传入绩效服务
        )
        await self.mock_trader.async_init()
        
        # 7. 创建插件上下文（用 MockTrader 和 MockPerformanceService）
        context = PluginContext(
            trader=self.mock_trader,
            stream_manager=None,  # 回测模式：显式传入 None
            database=session,
            cache=self.cache,
            rate_limiter=self.rate_limiter,
            trade_history_repo=TradeHistoryRepository(session),
            performance_service=self.mock_performance,  # 使用 Mock 绩效服务
            bot_config=self.bot_config_wrapper,  # 新增：传递 BotConfig
        )
        
        # 8. 构建工作流
        self.workflow_builder = builder
        self.graph = await builder.build(context)
        
        # 9. 计算总周期数
        cycle_interval = self.bot_config['bot']['cycle_interval_seconds']
        total_seconds = (self.end_date - self.start_date).total_seconds()
        self.total_cycles = int(total_seconds / cycle_interval)
        
        logger.info(f"✅ Backtest initialized")
        logger.info(f"   Total cycles: {self.total_cycles}")
        logger.info(f"   Cycle interval: {cycle_interval}s")
        
        return self
    
    def _get_default_symbols(self, exchange) -> List[str]:
        """获取默认回测币种（Top 5 by volume）"""
        markets = exchange.markets
        
        # 优先筛选 USDT/USDC 计价的永续合约
        symbols = [
            s for s, m in markets.items()
            if m.get('swap') and m.get('active') 
            and m.get('quote') in ('USDT', 'USDC', 'USD')
        ]
        
        # 如果没有找到，尝试更宽松的筛选（任何活跃的永续合约）
        if not symbols:
            symbols = [
                s for s, m in markets.items()
                if m.get('swap') and m.get('active')
            ]
        
        # 如果还是没有，尝试任何活跃市场
        if not symbols:
            symbols = [
                s for s, m in markets.items()
                if m.get('active')
            ]
        
        # 优先选择主流币种
        priority = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
        prioritized = []
        for p in priority:
            for s in symbols:
                if p in s.upper():
                    prioritized.append(s)
                    break
        
        # 补充其他币种到5个
        for s in symbols:
            if s not in prioritized:
                prioritized.append(s)
            if len(prioritized) >= 5:
                break
        
        logger.info(f"Default symbols selected: {prioritized[:5]}")
        return prioritized[:5]
    
    async def run(self):
        """运行回测"""
        logger.info("="*60)
        logger.info("🚀 Starting Backtest")
        logger.info("="*60)
        
        if self.max_cycles:
            logger.info(f"⚡ Fast mode: max {self.max_cycles} cycles")
        
        cycle_interval_ms = self.bot_config['bot']['cycle_interval_seconds'] * 1000
        
        while self.data_source.has_more_data():
            # 检查是否达到最大周期数
            if self.max_cycles and self.current_cycle >= self.max_cycles:
                logger.info(f"⚡ Reached max_cycles limit ({self.max_cycles}), stopping early")
                break
            
            self.current_cycle += 1
            
            # 进度报告（每10个周期，或每个周期如果 max_cycles < 10）
            report_interval = min(10, self.max_cycles or 10)
            if self.current_cycle % report_interval == 0 or self.current_cycle == 1:
                progress = (self.current_cycle / self.total_cycles) * 100 if self.total_cycles > 0 else 0
                logger.info(
                    f"📈 Progress: {progress:.1f}% "
                    f"(Cycle {self.current_cycle}/{self.total_cycles}, "
                    f"Balance: ${self.mock_trader.balance:.2f})"
                )
            
            # 获取当前状态
            account = await self.mock_trader.get_account_info()
            positions = await self.mock_trader.get_positions()
            
            # 创建 State（🔧 使用预加载的 symbols，跳过 coins_pick 的动态选币）
            state = State(
                bot_id=self.bot_id,
                prompt_name=self.bot_config['bot']['prompt'],
                account=account,
                positions=positions,
                initial_balance=self.initial_balance,
                symbols=self.preloaded_symbols  # 使用预加载的币种列表
            )
            
            # 运行工作流
            config = {
                "configurable": {
                    "thread_id": f"backtest_{self.bot_id}"
                }
            }
            
            try:
                await self.graph.ainvoke(state, config)
            except Exception as e:
                logger.error(f"❌ Cycle {self.current_cycle} failed: {e}")
            
            # 推进时间
            self.data_source.advance_time(cycle_interval_ms)
        
        # 生成报告
        report = await self.generate_report()
        
        logger.info("="*60)
        logger.info("🎉 Backtest Completed")
        logger.info("="*60)
        logger.info(f"Initial: ${self.initial_balance:.2f}")
        logger.info(f"Final: ${self.mock_trader.balance:.2f}")
        logger.info(f"Return: ${report['total_return']:.2f} ({report['return_pct']:.2f}%)")
        logger.info(f"Trades: {report['total_trades']}")
        logger.info(f"Win Rate: {report['win_rate']:.1f}%")
        logger.info(f"Sharpe: {report['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown: {report['max_drawdown']*100:.2f}%")
        logger.info("="*60)
        
        return report
    
    async def generate_report(self) -> dict:
        """生成回测报告"""
        # 🔧 使用 MockPerformanceService（纯内存，不依赖数据库）
        metrics = self.mock_performance.calculate_metrics(self.bot_id)
        
        total_return = self.mock_trader.balance - self.initial_balance
        return_pct = (total_return / self.initial_balance) * 100 if self.initial_balance > 0 else 0
        
        return {
            "total_return": total_return,
            "return_pct": return_pct,
            "final_balance": self.mock_trader.balance,
            "total_trades": metrics.total_trades,
            "win_rate": metrics.win_rate,
            "sharpe_ratio": metrics.sharpe_ratio,
            "max_drawdown": metrics.max_drawdown,
            "profit_factor": metrics.profit_factor,
        }
    
    async def cleanup(self):
        """清理资源"""
        logger.info("🧹 Cleaning up backtest resources...")
        
        if hasattr(self, 'workflow_builder'):
            await self.workflow_builder.cleanup()
        
        if hasattr(self, 'data_source') and hasattr(self.data_source, 'exchange'):
            await self.data_source.exchange.close()
        
        logger.info("✅ Cleanup completed")

