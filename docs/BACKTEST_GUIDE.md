# 回测系统使用指南

## 概述

LangTrader 回测系统基于 LangGraph Checkpoint 和 MockTrader 实现，完全复用现有工作流节点，支持时光旅行分析。

## 核心特性

### 1. 零侵入式设计
- ✅ 所有现有节点无需修改
- ✅ 复用 CoinsPick → MarketState → QuantSignalFilter → MarketAnalyzer → Decision → RiskMonitor → Execution 完整链路
- ✅ 相同的 Prompt、量化规则、风险管理

### 2. 时光旅行能力
- ✅ 每个周期的 Checkpoint 保存到 PostgreSQL
- ✅ 可回溯任意历史决策点
- ✅ 支持 What-If 分析（从检查点分叉）

### 3. API 友好
- ✅ 预加载机制：一次拉取所有历史数据
- ✅ 缓存持久化：7天 TTL，减少重复请求
- ✅ 限流保护：复用 RateLimiter
- ✅ 并发控制：Semaphore(5) 限制并发

## 快速开始

### 1. 执行数据库迁移

```bash
# 添加回测任务表
python scripts/apply_migration.py
# 或手动执行
psql $DATABASE_URL -f scripts/migrations/add_backtest_tables.sql
```

### 2. 运行回测

```bash
# 默认配置：Bot 1，最近7天，初始资金 $10,000
python examples/run_backtest.py
```

### 3. 自定义回测参数

修改 `examples/run_backtest.py`：

```python
# 配置回测参数
bot_id = 1
start_date = datetime(2024, 1, 1)      # 自定义开始日期
end_date = datetime(2024, 3, 31)       # 自定义结束日期
initial_balance = 50000                # 自定义初始资金

# 指定回测币种（可选）
symbols = ['BTC/USDT:USDT', 'ETH/USDT:USDT', 'SOL/USDT:USDT']

engine = BacktestEngine(
    bot_id=bot_id,
    start_date=start_date,
    end_date=end_date,
    initial_balance=initial_balance,
    symbols=symbols  # 如果不指定，使用 Top 5 by volume
)
```

## 架构设计

### 数据流

```
┌─────────────────────────────────────┐
│  真实交易所 (CCXT Pro)               │
│  └─ 预加载历史K线数据                │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  ExchangeBacktestDataSource         │
│  ├─ 按时间切片返回K线                │
│  └─ Cache 缓存（7天TTL）             │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  MockTrader (替换 Trader)            │
│  ├─ 虚拟账户余额                     │
│  ├─ 模拟订单撮合                     │
│  └─ 计算手续费/滑点                  │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  PluginContext                      │
│  └─ trader=MockTrader               │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  WorkflowBuilder                    │
│  └─ 复用所有现有节点                 │
└────────────┬────────────────────────┘
             ↓
┌─────────────────────────────────────┐
│  LangGraph 执行                     │
│  └─ Checkpoint 保存每个周期          │
└─────────────────────────────────────┘
```

### 关键组件

**MockTrader**:
- 实现与 `Trader` 完全相同的接口
- 维护虚拟账户状态（余额、持仓）
- 模拟订单撮合（基于当前K线价格）
- 考虑手续费（0.05%）和滑点（0.02%）

**BacktestDataSource**:
- 抽象基类，定义数据获取接口
- `ExchangeBacktestDataSource`：从交易所拉取
- `DatabaseBacktestDataSource`：从本地数据库读取（未来扩展）

**BacktestEngine**:
- 初始化：创建 MockTrader 和 PluginContext
- 预加载：批量拉取所有历史K线
- 时间循环：逐周期推进，运行工作流
- 报告生成：利用 PerformanceService

## 回测结果示例

```
====================================================
🎉 Backtest Completed
====================================================
Initial: $10,000.00
Final: $11,250.00
Return: $1,250.00 (+12.50%)
Trades: 45
Win Rate: 62.2%
Sharpe: 1.45
Max Drawdown: -8.50%
====================================================
```

## 时光旅行分析

### 查看历史 Checkpoint

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import os

async def analyze_checkpoints(bot_id: int):
    """分析历史决策检查点"""
    
    checkpointer = AsyncPostgresSaver.from_conn_string(os.getenv("DATABASE_URL"))
    async with checkpointer:
        # 列出所有回测的 Checkpoint
        checkpoints = []
        async for checkpoint in checkpointer.list(
            config={"configurable": {"thread_id": f"backtest_{bot_id}"}}
        ):
            checkpoints.append(checkpoint)
        
        print(f"Found {len(checkpoints)} checkpoints")
        
        # 查看特定周期的决策
        for checkpoint in checkpoints[:10]:  # 前10个周期
            state = checkpoint.values
            
            for symbol, run_record in state.get('runs', {}).items():
                if run_record.get('decision'):
                    decision = run_record['decision']
                    print(f"\nCycle: {run_record.get('cycle_id')}")
                    print(f"  Symbol: {symbol}")
                    print(f"  Action: {decision.get('action')}")
                    print(f"  Confidence: {decision.get('confidence')}")
                    print(f"  Reasons: {decision.get('reasons')}")

# 运行分析
asyncio.run(analyze_checkpoints(bot_id=1))
```

### 从特定点分叉测试

```python
# 从第100个周期开始，测试不同参数
checkpoint_100 = get_checkpoint(thread_id="backtest_1", checkpoint_id=100)

# 修改配置（例如更激进的仓位）
state_100 = checkpoint_100.state
state_100.bot_config['max_position_size_percent'] = 20  # 增加到20%

# 从这个点继续运行
result = await graph.ainvoke(state_100, config={...})
```

## 性能优化

### 1. 减少 API 请求

**预加载策略**：
```python
# 一次性拉取所有数据
await data_source.preload_data(
    symbols=['BTC/USDT:USDT', 'ETH/USDT:USDT'],
    timeframes=['3m', '4h']
)

# 后续 fetch_ohlcv 调用直接从内存切片
```

**缓存策略**：
```python
# 回测数据缓存 7 天
cache.set('backtest_ohlcv', ohlcv, cache_key)

# 二次运行相同参数的回测，零 API 请求
```

### 2. 控制并发

```python
# 预加载时控制并发数
semaphore = asyncio.Semaphore(5)  # 最多5个并发请求

async def fetch_with_semaphore(symbol, timeframe):
    async with semaphore:
        return await fetch_one(symbol, timeframe)
```

### 3. 限流保护

```python
# 复用 RateLimiter
if self.rate_limiter:
    await self.rate_limiter.wait_if_needed()

# 根据交易所速率自动调整
rate_limiter.set_rate_limit(exchange.rateLimit)
```

## 注意事项

### 1. 数据范围限制

- **短期回测（<30天）**：建议直接从交易所拉取
  - 优点：简单快速
  - 缺点：受 API 限制，数据量有限

- **长期回测（>30天）**：建议先下载到本地
  - 使用 `backtest_ohlcv_cache` 表
  - 批量导入历史数据

### 2. API 限制

不同交易所的限制：
- Binance: 1200 请求/分钟
- Bybit: 120 请求/分钟
- Hyperliquid: 600 请求/分钟

回测预加载阶段：
- 5个币种 × 2个时间框架 = 10个请求
- 使用 Semaphore(5) + RateLimiter 控制
- 预计耗时：10-30秒

### 3. 手续费和滑点

默认配置：
```python
commission = 0.0005  # 0.05% 手续费
slippage = 0.0002    # 0.02% 滑点
```

可在创建 MockTrader 时自定义：
```python
mock_trader = MockTrader(
    initial_balance=10000,
    data_source=data_source,
    commission=0.001,   # 0.1% 手续费
    slippage=0.0005     # 0.05% 滑点
)
```

### 4. 决策一致性

**LLM 温度参数**：
- 回测时建议设置 `temperature=0`（确定性输出）
- 在 `llm_configs` 表中配置

```sql
UPDATE llm_configs 
SET temperature = 0 
WHERE id = 1;
```

## 常见问题

### Q1: 回测速度慢？

**优化方案**：
1. 减少回测币种（5个而非20个）
2. 使用更短的时间范围（7天而非30天）
3. 预加载数据到数据库（避免重复拉取）

### Q2: 回测结果与实盘差异大？

**可能原因**：
1. LLM 温度参数不同（实盘>0，回测=0）
2. 滑点和手续费设置不准确
3. 回测未考虑流动性不足（大单冲击成本）
4. 市场环境变化（历史表现不代表未来）

### Q3: 如何验证回测准确性？

**验证方法**：
1. 对比相同周期的纸上交易结果
2. 检查 Checkpoint 中的决策逻辑
3. 手动验证几笔交易的盈亏计算
4. 对比不同参数的回测结果

## 未来扩展

### 1. 参数优化器

```python
class ParameterOptimizer:
    """参数优化器（网格搜索）"""
    
    async def optimize(self, param_grid):
        results = []
        
        for leverage in [1, 3, 5]:
            for threshold in [40, 50, 60]:
                # 修改配置
                bot_config['max_leverage'] = leverage
                bot_config['quant_signal_threshold'] = threshold
                
                # 运行回测
                report = await engine.run()
                
                results.append({
                    'leverage': leverage,
                    'threshold': threshold,
                    'sharpe': report['sharpe_ratio']
                })
        
        # 找出最优参数
        best = max(results, key=lambda x: x['sharpe'])
        return best
```

### 2. 多策略对比

```python
# 对比不同 Workflow 的表现
workflows = [1, 2, 3]  # 不同策略ID

for workflow_id in workflows:
    bot_config['workflow_id'] = workflow_id
    report = await engine.run()
    print(f"Workflow {workflow_id}: Sharpe={report['sharpe_ratio']}")
```

### 3. Walk-Forward 分析

```python
# 滚动窗口回测
for i in range(12):  # 12个月
    start = datetime(2024, i+1, 1)
    end = start + timedelta(days=30)
    
    engine = BacktestEngine(bot_id=1, start_date=start, end_date=end)
    report = await engine.run()
    
    print(f"Month {i+1}: Return={report['return_pct']:.2f}%")
```

## 技术细节

### Checkpoint 存储

```sql
-- 查看回测的 Checkpoint
SELECT 
    thread_id, 
    checkpoint_id, 
    metadata->>'step' as step,
    metadata->>'timestamp' as timestamp
FROM checkpoints
WHERE thread_id LIKE 'backtest_%'
ORDER BY checkpoint_id DESC
LIMIT 10;
```

### 交易记录

回测的交易会正常记录到 `trade_history` 表：

```sql
-- 查看回测交易记录
SELECT 
    symbol, 
    side, 
    action,
    entry_price,
    exit_price,
    pnl_percent,
    opened_at
FROM trade_history
WHERE bot_id = 1
  AND cycle_id LIKE 'backtest_%'
ORDER BY opened_at DESC;
```

## 总结

LangTrader 回测系统完美融合了：
- LangGraph 的时光旅行能力
- LLM 驱动的决策逻辑
- 量化规则的预处理
- 动态风险管理

零侵入式设计确保回测结果与实盘高度一致，是验证和优化策略的理想工具。🚀

---

**最后更新**: 2025-12-30
**版本**: v1.0.0

