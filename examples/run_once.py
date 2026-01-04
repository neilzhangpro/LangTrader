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
from langtrader_core.data.models.bot import Bot
from langtrader_core.utils import get_logger
from langtrader_core.graph.state import State
from langtrader_core.services.trader import Trader
from langtrader_core.services.stream_manager import DynamicStreamManager
from langtrader_core.services.container import ServiceContainer
from langtrader_core.services.config_manager import BotConfig
from langtrader_core.services.performance import PerformanceService
from langtrader_core.data.repositories.trade_history import TradeHistoryRepository
from langtrader_core.plugins.registry import registry, PluginContext
from langtrader_core.plugins.workflow import WorkflowBuilder
from langtrader_core.services.status_file import write_bot_status, mark_bot_stopped
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
        self.cycle = 0  # 当前周期数
        self.last_error = None  # 最后一次错误
        
        # ✅ 使用服务容器管理共享实例
        self.container = ServiceContainer.get_instance(self.session)
        self.cache = self.container.get_cache()
        self.rate_limiter = self.container.get_rate_limiter()

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
        
        # 加载 Bot 模型（用于 BotConfig）
        bot_model = self.session.get(Bot, self.bot_id)
        self.bot_config_wrapper = BotConfig(bot_model)
        
        logger.info(f"✅ Bot: {self.bot_config['name']}")
        logger.info(f"✅ Exchange: {self.exchange_config['name']}")
        logger.info(f"✅ Workflow: {self.workflow_config['name']}")
        logger.info(f"✅ Trading Mode: {self.bot_config['trading_mode']}")
        logger.info(f"✅ Timeframes: {self.bot_config_wrapper.timeframes}")
        
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
        
        # 6. 创建插件上下文（包含共享实例和配置）
        context = PluginContext(
            trader=self.trader,
            stream_manager=self.stream_manager,
            database=self.session,
            cache=self.cache,
            rate_limiter=self.rate_limiter,
            trade_history_repo=self.trade_history_repo,
            performance_service=self.performance_service,
            bot_config=self.bot_config_wrapper,  # 新增：传递 BotConfig
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
        
        # 10. 根据 cycle_interval 动态调整缓存 TTL
        interval = self.bot_config['cycle_interval_seconds']
        self.cache.set_cycle_interval(interval)
        
        logger.info("✅ Async initialization completed")
        logger.info(f"   Initial balance: {self.initial_balance} USDC")
        logger.info(f"   Initial positions: {len(self.positions)}")
        logger.info(f"   Cycle interval: {interval}s")
        
        return self

    async def run(self):
        """运行交易周期"""
        logger.info(f"🔄 Running trading cycle...")
        
        # ========== 每轮开始：重置状态 ==========
        # 1. 清理临时数据（避免上一轮数据残留）
        self.state.reset_for_new_cycle()
        logger.debug("State reset for new cycle")
        
        # 2. 清理过期缓存（防止内存无限增长）
        cleaned = self.cache.cleanup_expired()
        if cleaned > 0:
            logger.debug(f"🧹 Cleaned {cleaned} expired cache entries")
        
        # 3. 刷新账户和持仓（从交易所获取最新状态）
        try:
            self.state.account = await self.trader.get_account_info()
            self.state.positions = await self.trader.get_positions()
            balance = self.state.account.total.get('USDC', 0) or self.state.account.total.get('USDT', 0)
            logger.info(f"📊 Refreshed: balance={balance:.2f}, positions={len(self.state.positions)}")
        except Exception as e:
            logger.error(f"❌ Failed to refresh account/positions: {e}")
        
        # 4. 刷新数据库会话（避免过期连接）
        self.session.expire_all()
        
        # ========== 运行工作流 ==========
        config: RunnableConfig = {
            "configurable": {
                "thread_id": f"bot_{self.bot_id}"
            }
        }
        
        # 运行图（带追踪支持）
        builder = self.workflow_builder
        result_dict = await builder.run_with_tracing(self.state, config)
        
        # 更新状态（工作流返回的结果）
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
        
        # ========== 写入状态文件（供 API 读取）==========
        self._write_status_file(state="running")
        
        return self.state
    
    def _write_status_file(self, state: str = "running", last_error: str = None):
        """
        写入状态文件，供 API 读取 bot 运行状态
        
        Args:
            state: 运行状态 ('running', 'idle', 'error', 'stopped')
            last_error: 最后一次错误信息
        """
        try:
            # 获取余额
            balance = 0.0
            if self.state.account:
                balance = self.state.account.total.get('USDC', 0) or self.state.account.total.get('USDT', 0)
            
            # 获取最后决策摘要
            last_decision = None
            if self.state.batch_decision:
                decisions = self.state.batch_decision.decisions
                if decisions:
                    # 简化为：symbol:action 列表
                    last_decision = ", ".join([f"{d.symbol}:{d.action}" for d in decisions[:3]])
                    if len(decisions) > 3:
                        last_decision += f"... (+{len(decisions)-3})"
            
            write_bot_status(
                bot_id=self.bot_id,
                cycle=self.cycle,
                balance=balance,
                initial_balance=self.initial_balance,
                positions=self.state.positions or [],
                symbols=self.state.symbols or [],
                state=state,
                last_decision=last_decision,
                last_error=last_error or self.last_error,
            )
        except Exception as e:
            logger.warning(f"Failed to write status file: {e}")

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
        consecutive_failures = 0
        max_consecutive_failures = 5  # 连续失败 5 次后退出
        
        while True:
            cycle += 1
            logger.info("\n" + "=" * 60)
            logger.info(f"🔁 CYCLE #{cycle} - {datetime.now()}")
            logger.info("=" * 60)
            
            # 每 50 个周期刷新数据库 Session，避免连接老化
            if cycle > 1 and cycle % 50 == 0:
                logger.info("🔄 Refreshing database session (every 50 cycles)...")
                run_once.session.close()
                run_once.session = SessionLocal()
                run_once.container.session = run_once.session
            
            # 周期级别错误隔离：单个周期失败不会导致程序退出
            run_once.cycle = cycle  # 同步周期数
            try:
                await run_once.run()
                consecutive_failures = 0  # 成功后重置计数
                run_once.last_error = None
            except Exception as e:
                consecutive_failures += 1
                run_once.last_error = str(e)[:200]  # 记录错误（截断）
                logger.error(f"❌ Cycle #{cycle} failed ({consecutive_failures}/{max_consecutive_failures}): {e}", 
                           exc_info=True)
                
                # 写入错误状态
                run_once._write_status_file(state="error", last_error=run_once.last_error)
                
                # 连续失败熔断：超过阈值则退出
                if consecutive_failures >= max_consecutive_failures:
                    logger.critical(f"💀 Too many consecutive failures ({max_consecutive_failures}), shutting down...")
                    break
                
                logger.warning(f"⚠️ Skipping this cycle, will retry in {interval}s...")
            
            logger.info(f"\n⏳ Sleeping {interval}s until next cycle...")
            await asyncio.sleep(interval)
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
    
    finally:
        # 标记 bot 为已停止
        mark_bot_stopped(run_once.bot_id)
        await run_once.cleanup()
        logger.info("👋 Program ended")


if __name__ == "__main__":
    asyncio.run(main())
