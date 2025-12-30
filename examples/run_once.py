# examples/run_once.py
"""
交易系统运行入口
基于数据库配置运行交易机器人
"""
import sys
from pathlib import Path
import asyncio

# add packages directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.data import SessionLocal, init_db
from langtrader_core.utils import get_logger
from langtrader_core.graph.state import State
from langtrader_core.services.trader import Trader
from langtrader_core.services.stream_manager import DynamicStreamManager
from langtrader_core.services.cache import Cache
from langtrader_core.services.ratelimit import RateLimiter
from langtrader_core.services.performance import PerformanceService
from langtrader_core.data.repositories.trade_history import TradeHistoryRepository
from langtrader_core.plugins.registry import registry, PluginContext
from langtrader_core.plugins.workflow import WorkflowBuilder
from datetime import datetime
from langchain_core.runnables import RunnableConfig

logger = get_logger("run_once")


class RunOnce:
    """
    交易系统运行器（基于数据库配置）
    """
    
    def __init__(self, bot_id: int = 1):
        """
        初始化
        
        Args:
            bot_id: 要运行的 Bot ID
        """
        # 初始化数据库
        init_db()
        self.session = SessionLocal()
        self.bot_id = bot_id
        self.graph = None
        
        # ✅ 在初始化时创建共享实例
        self.cache = Cache()
        self.rate_limiter = RateLimiter()

    async def async_init(self):
        """异步初始化"""
        logger.info("Starting async initialization...")
        
        # 1. 加载 Bot 配置（包括 Exchange 和 Workflow）
        logger.info(f"📦 Loading bot configuration: bot_id={self.bot_id}")
        
        builder = WorkflowBuilder(self.session, self.bot_id)
        config = builder.load_bot_config()
        
        # 提取配置
        self.bot_config = config['bot']
        self.exchange_config = config['exchange']
        self.workflow_config = config['workflow']
        
        logger.info(f"✅ Bot: {self.bot_config['name']}")
        logger.info(f"✅ Exchange: {self.exchange_config['name']}")
        logger.info(f"✅ Workflow: {self.workflow_config['name']}")
        logger.info(f"✅ Trading Mode: {self.bot_config['trading_mode']}")
        
        # 2. 初始化 Trader
        self.trader = Trader(self.exchange_config)
        await self.trader.async_init()
        
        # ✅ 设置限流器的速率限制
        if self.trader.exchange:
            self.rate_limiter.set_rate_limit(self.trader.exchange.rateLimit)
        
        # 3. 初始化 Stream Manager
        logger.info("Initializing dynamic stream manager...")
        self.stream_manager = DynamicStreamManager(self.trader)
        
        # 4. 获取账户信息
        _account_info = await self.trader.get_account_info()
        self.initial_balance = _account_info.total.get('USDC', 0)
        self.positions = await self.trader.get_positions()
        
        # 5. 初始化交易历史仓储和绩效服务
        logger.info("Initializing trade history and performance services...")
        self.trade_history_repo = TradeHistoryRepository(self.session)
        self.performance_service = PerformanceService(self.session)
        
        # 6. 创建插件上下文（包含共享实例）
        context = PluginContext(
            trader=self.trader,
            stream_manager=self.stream_manager,
            database=self.session,
            cache=self.cache,
            rate_limiter=self.rate_limiter,
            trade_history_repo=self.trade_history_repo,
            performance_service=self.performance_service,
        )
        
        # 7. 列出已发现的插件
        logger.info("🔍 Listing plugins...")
        plugins = registry.list_plugins() 
        logger.info(f"✅ Discovered {len(plugins)} plugins")
        for plugin in plugins:
            logger.info(f"   - {plugin.name} (v{plugin.version}) by {plugin.author}")
        
        # 8. 构建工作流
        logger.info("🏗️  Building workflow...")
        self.workflow_builder = builder  # 保存 builder 引用以支持追踪
        self.graph = await builder.build(context)

        if self.graph is None:
            logger.error(f'🚨🚨 graph not built yet!')
            raise ValueError(f'🚨🚨 graph not built yet!')
        
        # 9. 初始化 State
        self.state = State(
            bot_id=self.bot_id,
            prompt_name = self.bot_config['prompt'], # prompt template
            account=_account_info,
            positions=self.positions,
            initial_balance=self.initial_balance,
        )
        
        logger.info("✅ Async initialization completed")
        logger.info(f"   Initial balance: {self.initial_balance} USDC")
        logger.info(f"   Initial positions: {len(self.positions)}")
        
        return self

    async def run(self):
        """运行交易周期"""
        logger.info(f"🔄 Running trading cycle...")
        
        config: RunnableConfig = {
            "configurable": {
                "thread_id": f"bot_{self.bot_id}"
            }
        }
        
        # 运行图（带追踪支持）
        builder = self.workflow_builder
        result_dict = await builder.run_with_tracing(self.state, config)
        
        # 更新状态
        if result_dict and isinstance(result_dict, dict):
            if 'symbols' in result_dict:
                self.state.symbols = result_dict['symbols']
                logger.info(f"✓ Updated symbols: {len(self.state.symbols)} coins")
            
            if 'account' in result_dict:
                self.state.account = result_dict['account']
            
            if 'positions' in result_dict:
                self.state.positions = result_dict['positions']
                logger.info(f"✓ Updated positions: {len(self.state.positions)}")
        
        logger.info(f"Current state: {len(self.state.symbols)} symbols selected")
        return self.state

    async def cleanup(self):
        """清理资源"""
        logger.info("🧹 Cleaning up resources...")

        # 1. 关闭 WebSocket streams
        if hasattr(self, 'stream_manager'):
            logger.info("Shutting down WebSocket streams...")
            await self.stream_manager.shutdown()

        # 2. 关闭 Exchange 连接
        if hasattr(self, 'trader'):
            logger.info("Closing exchange connection...")
            await self.trader.close()

        # 3. 清理 WorkflowBuilder（关闭 PostgreSQL checkpointer）
        if hasattr(self, 'workflow_builder') and self.workflow_builder:
            logger.info("Cleaning up workflow builder...")
            await self.workflow_builder.cleanup()

        # 4. 关闭数据库 session
        if hasattr(self, 'session'):
            logger.info("Closing database session...")
            self.session.close()

        logger.info("✅ Cleanup completed")


async def main():
    """主入口"""
    # 指定要运行的 Bot ID（可以从命令行参数读取）
    bot_id = 1  # 使用 test_bot_paper
    
    run_once = RunOnce(bot_id=bot_id)
    
    try:
        # 初始化
        logger.info("=" * 60)
        logger.info("🚀 INITIALIZING TRADING SYSTEM")
        logger.info("=" * 60)
        await run_once.async_init()
        
        # 定时循环
        logger.info("\n" + "=" * 60)
        logger.info("⏰ STARTING TIMER LOOP")
        logger.info("=" * 60)
        
        # 使用 bot 配置的周期间隔
        interval = run_once.bot_config['cycle_interval_seconds']
        logger.info(f"Cycle interval: {interval}s")
        
        cycle = 0
        
        while True:
            cycle += 1
            logger.info("\n" + "=" * 60)
            logger.info(f"🔁 CYCLE #{cycle} - {datetime.now()}")
            logger.info("=" * 60)
            
            await run_once.run()
            
            logger.info(f"\n⏳ Sleeping {interval}s until next cycle...")
            await asyncio.sleep(interval)
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    
    finally:
        await run_once.cleanup()
        logger.info("👋 Program ended")


if __name__ == "__main__":
    asyncio.run(main())
