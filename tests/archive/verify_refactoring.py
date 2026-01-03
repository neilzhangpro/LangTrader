#!/usr/bin/env python3
"""
验证重构后的系统集成
"""
import sys
from pathlib import Path

# Add packages to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))

from langtrader_core.data import SessionLocal, init_db
from langtrader_core.data.models.bot import Bot
from langtrader_core.services.config_manager import SystemConfig, BotConfig
from langtrader_core.services.container import ServiceContainer


def test_system_config():
    """测试系统配置加载"""
    print("\n" + "="*60)
    print("测试 1: 系统配置加载")
    print("="*60)
    
    init_db()
    session = SessionLocal()
    
    try:
        # 加载配置
        configs = SystemConfig.load(session)
        print(f"✓ 加载了 {len(configs)} 条系统配置")
        
        # 测试获取缓存TTL
        ttl = SystemConfig.get_cache_ttl('orderbook')
        print(f"✓ 订单簿缓存TTL: {ttl}秒")
        
        # 获取所有缓存TTL
        all_ttls = SystemConfig.get_all_cache_ttls()
        print(f"✓ 缓存配置类型: {len(all_ttls)} 个")
        
        return True
    except Exception as e:
        print(f"✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_bot_config():
    """测试 Bot 配置"""
    print("\n" + "="*60)
    print("测试 2: Bot 配置加载")
    print("="*60)
    
    init_db()
    session = SessionLocal()
    
    try:
        # 加载 Bot
        bot = session.get(Bot, 1)
        if not bot:
            print("✗ Bot 1 不存在")
            return False
        
        print(f"✓ 加载 Bot: {bot.name}")
        
        # 创建配置包装器
        bot_config = BotConfig(bot)
        
        # 测试配置访问
        timeframes = bot_config.timeframes
        print(f"✓ 时间框架: {timeframes}")
        
        for tf in timeframes:
            limit = bot_config.get_ohlcv_limit(tf)
            print(f"  - {tf}: {limit} 根K线")
        
        # 测试指标配置
        ema_periods = bot_config.get_ema_periods()
        print(f"✓ EMA 周期: {ema_periods}")
        
        rsi_period = bot_config.get_rsi_period()
        print(f"✓ RSI 周期: {rsi_period}")
        
        required_length = bot_config.get_required_ohlcv_length()
        print(f"✓ 所需最小K线数量: {required_length}")
        
        return True
    except Exception as e:
        print(f"✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_service_container():
    """测试服务容器"""
    print("\n" + "="*60)
    print("测试 3: 服务容器")
    print("="*60)
    
    init_db()
    session = SessionLocal()
    
    try:
        # 获取容器
        container = ServiceContainer.get_instance(session)
        print("✓ 服务容器初始化")
        
        # 获取服务
        cache = container.get_cache()
        print(f"✓ Cache 服务: {type(cache).__name__}")
        
        rate_limiter = container.get_rate_limiter()
        print(f"✓ RateLimiter 服务: {type(rate_limiter).__name__}")
        
        system_config = container.get_system_config()
        print(f"✓ SystemConfig 服务: {type(system_config).__name__}")
        
        # 验证是单例
        container2 = ServiceContainer.get_instance()
        if container is container2:
            print("✓ 容器单例模式正常")
        else:
            print("✗ 容器单例模式失败")
            return False
        
        return True
    except Exception as e:
        print(f"✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


def test_backward_compatibility():
    """测试向后兼容性"""
    print("\n" + "="*60)
    print("测试 4: 向后兼容性")
    print("="*60)
    
    try:
        from langtrader_core.services.cache import Cache
        from langtrader_core.services.ratelimit import RateLimiter
        from langtrader_core.services.market import Market
        
        # 测试旧方式仍然工作
        cache = Cache()  # 无 session 参数
        print("✓ Cache() 无参数调用仍然工作")
        
        rate_limiter = RateLimiter()
        print("✓ RateLimiter() 仍然工作")
        
        # Market 可以不传 bot_config
        market = Market(trader=None, stream_manager=None, cache=cache, rate_limiter=rate_limiter)
        print("✓ Market 可以不传 bot_config")
        
        return True
    except Exception as e:
        print(f"✗ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "🔍 系统重构验证".center(60, "="))
    print("验证配置管理重构是否成功集成\n")
    
    results = []
    
    results.append(test_system_config())
    results.append(test_bot_config())
    results.append(test_service_container())
    results.append(test_backward_compatibility())
    
    print("\n" + "="*60)
    print("验证结果汇总")
    print("="*60)
    print(f"总测试数: {len(results)}")
    print(f"通过: {sum(results)}")
    print(f"失败: {len(results) - sum(results)}")
    
    if all(results):
        print("\n✅ 所有验证测试通过！")
        print("\n重构成果:")
        print("  ✓ 系统配置从数据库加载")
        print("  ✓ Bot 配置支持动态时间框架")
        print("  ✓ 服务容器统一管理依赖")
        print("  ✓ 向后兼容性保持")
        print("\n下一步:")
        print("  1. 运行实盘测试验证")
        print("  2. 运行回测验证动态配置")
        print("  3. 通过 SQL 修改配置并观察效果")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)

