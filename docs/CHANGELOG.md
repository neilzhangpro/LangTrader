# 📋 Changelog / 更新日志

All notable changes to this project will be documented in this file.

本文件记录项目的所有重要更新。

---

## [Unreleased]

## [0.2.0] - 2026-01-04

### 🔧 稳定性优化 / Stability Improvements

#### LangChain Runnables 重构
- **Phase 2 并行优化**: 将错误的 `abatch([单个输入])` 替换为 `RunnableParallel`，实现真正的 Bull/Bear 并行分析
- **with_fallbacks 机制**: 为所有 LLM 调用添加 fallback 保护，提高容错能力
- **超时处理**: 结合 `asyncio.wait_for` 和 `with_fallbacks` 实现完善的超时保护

#### 内存泄漏修复
- **Cache 定期清理**: 添加 `cleanup_expired()` 方法，每个交易周期主动清理过期缓存条目
- **订阅锁清理**: 取消 WebSocket 订阅时自动清理对应的 `asyncio.Lock`，防止锁对象累积

#### WebSocket 流管理优化
- **失败重试机制**: 添加 `_failed_symbols` 追踪，失败的币种在下一轮 `sync_subscriptions` 时自动重试
- **统计信息增强**: 新增 `failed_retries` 统计项

#### 数据库连接管理
- **Session 定期刷新**: 每 50 个交易周期自动刷新数据库 Session，避免长连接老化问题

### 📁 文件变更 / Changed Files

| 文件 | 变更内容 |
|------|---------|
| `packages/langtrader_core/graph/nodes/debate_decision.py` | RunnableParallel + with_fallbacks 重构 |
| `packages/langtrader_core/graph/nodes/batch_decision.py` | with_fallbacks 添加 |
| `packages/langtrader_core/services/cache.py` | 添加 `cleanup_expired()` 方法 |
| `packages/langtrader_core/services/stream_manager.py` | 锁清理 + 失败重试机制 |
| `examples/run_once.py` | 缓存清理 + Session 刷新 |

---

## [0.1.0] - 2026-01-02

### 🎉 初始版本 / Initial Release

- **LangGraph StateGraph 工作流**: 支持热插拔节点架构
- **多 Agent 辩论模式**: 4 角色（分析师/多头/空头/风控）协作决策
- **70+ 交易所支持**: 基于 CCXT Pro 统一接口
- **量化信号引擎**: 趋势/动量/波动率/成交量多维度分析
- **PostgreSQL 配置管理**: 60 秒热重载
- **WebSocket 实时数据流**: 动态订阅管理
- **智能风控系统**: 敞口限制、连续亏损熔断、执行失败反馈

---

## 版本号说明 / Versioning

本项目遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/)：

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向下兼容的功能新增
- **PATCH**: 向下兼容的问题修复

