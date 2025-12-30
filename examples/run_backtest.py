#!/usr/bin/env python3
"""
回测运行示例
"""
import sys
from pathlib import Path
import asyncio
from datetime import datetime, timedelta

# 添加路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.data import SessionLocal, init_db
from langtrader_core.backtest.engine import BacktestEngine
from langtrader_core.utils import get_logger

logger = get_logger("run_backtest")


async def main():
    """主入口"""
    
    # 初始化数据库
    init_db()
    session = SessionLocal()
    
    # 配置回测参数
    bot_id = 1
    start_date = datetime.now() - timedelta(days=7)  # 最近7天
    end_date = datetime.now()
    initial_balance = 10000
    max_cycles = 5  # ⚡ 快速测试：限制最大周期数（设为 None 则运行全部周期）
    
    logger.info("="*60)
    logger.info("📊 LangTrader Backtest System")
    logger.info("="*60)
    logger.info(f"Bot ID: {bot_id}")
    logger.info(f"Period: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}")
    logger.info(f"Initial Balance: ${initial_balance}")
    logger.info(f"Max Cycles: {max_cycles or 'unlimited'}")
    
    # 创建回测引擎
    engine = BacktestEngine(
        bot_id=bot_id,
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance,
        max_cycles=max_cycles  # 限制周期数用于快速测试
    )
    
    try:
        # 初始化
        await engine.initialize(session)
        
        # 运行回测
        report = await engine.run()
        
        # 显示报告
        logger.info("\n" + "="*60)
        logger.info("📈 Backtest Report")
        logger.info("="*60)
        logger.info(f"Initial Balance:  ${engine.initial_balance:,.2f}")
        logger.info(f"Final Balance:    ${report['final_balance']:,.2f}")
        logger.info(f"Total Return:     ${report['total_return']:,.2f}")
        logger.info(f"Return %:         {report['return_pct']:+.2f}%")
        logger.info("-"*60)
        logger.info(f"Total Trades:     {report['total_trades']}")
        logger.info(f"Win Rate:         {report['win_rate']:.1f}%")
        logger.info(f"Sharpe Ratio:     {report['sharpe_ratio']:.2f}")
        logger.info(f"Max Drawdown:     {report['max_drawdown']:.2f}%")
        logger.info(f"Profit Factor:    {report['profit_factor']:.2f}")
        logger.info("="*60)
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Backtest failed: {e}", exc_info=True)
    finally:
        await engine.cleanup()
        session.close()
        logger.info("👋 Backtest ended")


if __name__ == "__main__":
    asyncio.run(main())

