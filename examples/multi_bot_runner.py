#!/usr/bin/env python3
"""
多 Bot 并发运行器
支持在同一进程内并发运行多个交易机器人
"""
import sys
from pathlib import Path
import asyncio
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# 添加路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))
sys.path.insert(0, str(project_root))  # ← 添加这一行

from langtrader_core.utils import get_logger

# 🎯 直接导入 RunOnce（现在 examples 在路径中）
from examples.run_once import RunOnce

logger = get_logger("multi_bot_runner")


class MultiBotRunner:
    """
    多 Bot 并发运行器
    管理多个 Bot 的生命周期和并发执行
    """
    
    def __init__(self, bot_ids: List[int]):
        """
        初始化多 Bot 运行器
        
        Args:
            bot_ids: 要运行的 Bot ID 列表
        """
        self.bot_ids = bot_ids
        self.runners: Dict[int, RunOnce] = {}
    
    async def initialize_all(self):
        """
        并发初始化所有 Bot
        
        注意：
        - 如果 Bot 共享 workflow，auto_sync 有锁保护，串行执行
        - 如果 Bot 使用独立 workflow，可以完全并发
        """
        logger.info("=" * 60)
        logger.info(f"🚀 Initializing {len(self.bot_ids)} bots concurrently...")
        logger.info("=" * 60)
        
        # 创建所有 Bot 实例
        for bot_id in self.bot_ids:
            runner = RunOnce(bot_id=bot_id)
            self.runners[bot_id] = runner
        
        # 🎯 并发初始化（auto_sync 内部有锁保护，安全）
        tasks = [runner.async_init() for runner in self.runners.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 检查初始化结果
        success_count = 0
        for bot_id, result in zip(self.bot_ids, results):
            if isinstance(result, Exception):
                logger.error(f"❌ Bot {bot_id} initialization failed: {result}")
                # 移除失败的 Bot
                del self.runners[bot_id]
            else:
                logger.info(f"✅ Bot {bot_id} initialized successfully")
                success_count += 1
        
        logger.info(f"\n✅ {success_count}/{len(self.bot_ids)} bots initialized successfully")
        
        if success_count == 0:
            raise RuntimeError("❌ No bots initialized successfully")
    
    async def run_all_cycles(self):
        """
        并发运行所有 Bot 的交易周期
        每个 Bot 按自己的 cycle_interval 独立运行
        """
        logger.info("\n" + "=" * 60)
        logger.info("⏰ STARTING MULTI-BOT TIMER LOOP")
        logger.info("=" * 60)
        
        # 为每个 Bot 创建独立的循环任务
        tasks = []
        for bot_id, runner in self.runners.items():
            tasks.append(self._run_bot_loop(bot_id, runner))
        
        # 🎯 并发运行所有 Bot 的循环
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _run_bot_loop(self, bot_id: int, runner: RunOnce):
        """
        单个 Bot 的循环任务
        
        Args:
            bot_id: Bot ID
            runner: RunOnce 实例
        """
        interval = runner.bot_config['cycle_interval_seconds']
        cycle = 0
        
        logger.info(f"🤖 Bot {bot_id} starting with {interval}s interval")
        
        try:
            while True:
                cycle += 1
                logger.info(f"\n[Bot {bot_id}] 🔁 CYCLE #{cycle}")
                
                try:
                    await runner.run()
                    logger.info(f"[Bot {bot_id}] ✅ Cycle #{cycle} completed")
                except Exception as e:
                    logger.error(f"[Bot {bot_id}] ❌ Cycle #{cycle} failed: {e}")
                
                logger.info(f"[Bot {bot_id}] ⏳ Sleeping {interval}s...")
                await asyncio.sleep(interval)
        
        except asyncio.CancelledError:
            logger.info(f"[Bot {bot_id}] 🛑 Cancelled")
            raise
        except Exception as e:
            logger.error(f"[Bot {bot_id}] ❌ Fatal error: {e}")
            raise
    
    async def cleanup_all(self):
        """清理所有 Bot 资源"""
        logger.info("\n" + "=" * 60)
        logger.info("🧹 Cleaning up all bots...")
        logger.info("=" * 60)
        
        tasks = []
        for bot_id, runner in self.runners.items():
            logger.info(f"Cleaning up bot {bot_id}...")
            tasks.append(runner.cleanup())
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("✅ All bots cleaned up")


async def main():
    """
    主入口：运行多个 Bot
    """
    # 🎯 指定要运行的 Bot IDs
    # 可以从命令行参数读取：python multi_bot_runner.py 1 2 3
    if len(sys.argv) > 1:
        bot_ids = [int(arg) for arg in sys.argv[1:]]
    else:
        # 默认运行 Bot 1
        bot_ids = [1]
    
    logger.info(f"🎯 Target bots: {bot_ids}")
    
    runner = MultiBotRunner(bot_ids)
    
    try:
        # 初始化所有 Bot
        await runner.initialize_all()
        
        # 运行所有 Bot（无限循环）
        await runner.run_all_cycles()
    
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    
    finally:
        await runner.cleanup_all()
        logger.info("👋 All bots stopped")


if __name__ == "__main__":
    asyncio.run(main())

