# 📋 Changelog / 更新日志

All notable changes to this project will be documented in this file.

本文件记录项目的所有重要更新。

---

## [Unreleased]

### ✨ 新增功能 / New Features

#### 辩论插件多 LLM 支持
- **角色级 LLM 配置**: `debate_decision` 插件支持为不同角色（analyst、bull、bear、risk_manager）配置专用的 LLM 模型
- **灵活的模型分配**: 可通过工作流节点配置为每个角色选择不同的 LLM，例如分析师使用 GPT-4o，多头交易员使用 Claude，空头交易员使用 GPT-4o-mini
- **Bot 详情页可视化**: 在 Bot 详情页的 AI Debate 标签中，每个角色卡片标题会显示其使用的 LLM 模型名称，便于快速了解角色配置

#### 工作流节点配置增强
- **JSON 配置支持**: 工作流编辑器中的节点配置面板支持直接编辑 JSON 格式的配置，为插件提供更灵活的配置能力
- **配置持久化**: 节点配置以 JSON 格式存储在数据库中，支持复杂的嵌套配置结构

### 📁 文件变更 / Changed Files

| 文件 | 变更内容 |
|------|---------|
| `packages/langtrader_core/graph/nodes/debate_decision.py` | 支持从节点配置读取角色级 LLM ID |
| `frontend/components/bots/debate-viewer.tsx` | 显示角色使用的 LLM 模型名称 |
| `frontend/app/bots/[id]/page.tsx` | 添加 workflow 和 LLM 配置查询，计算角色 LLM 映射 |
| `frontend/components/workflows/workflow-editor.tsx` | 添加 `config` 类型定义 |
| `frontend/components/workflows/workflow-canvas.tsx` | 添加 `config` 类型定义 |
| `frontend/components/workflows/node-config-panel.tsx` | 支持 JSON 配置编辑 |

## [0.3.0] - 2026-01-07

### 🎉 重大更新 / Major Updates

#### Next.js 前端界面
完整的 Web 管理界面，提供直观的交互体验：

- **Bot 管理**: 创建、编辑、启动、停止、删除交易机器人
- **实时监控**: 状态徽章、周期计数、余额更新、日志实时查看
- **AI 决策可视化**: 
  - 辩论模式：展示分析师报告、多空双方辩论过程
  - 批量决策：显示各币种决策结果和理由
- **交易历史**: 按 Bot 或全部查看交易记录
- **持仓展示**: 实时盈亏百分比、入场价、标记价
- **工作流编辑器**: 可视化拖拽编辑、节点配置面板
- **设置管理**: 交易所 API 配置、LLM 提供商配置、系统参数配置

#### Docker 一键部署
```bash
docker compose up -d --build
```
包含 PostgreSQL、FastAPI 后端、Next.js 前端的完整部署方案。

#### 多 Bot 并发运行
解决了多个 Bot 同时启动时相互阻塞的问题，支持同时运行多个交易机器人。

### ✨ 新增功能 / New Features

- **TanStack Query 数据管理**: 前端使用 React Query 实现高效的缓存和状态管理
- **WebSocket 实时更新**: 前端通过 WebSocket 接收实时交易数据
- **响应式设计**: 适配桌面端的现代化 UI 设计
- **暗色主题**: 专业的深色交易界面

### 🐛 Bug 修复 / Bug Fixes

#### 前端修复
- 修复 Bot 状态徽章在停止后不更新的问题（使用 `refetchQueries` 替代 `invalidateQueries`）
- 修复 Edit Bot 对话框因空值调用 `.toString()` 导致的崩溃
- 修复 LLM Config 下拉框空值 `""` 导致的 Radix UI 错误（改用 `"none"`）
- 修复工作流编辑页面缓存问题（不同 ID 显示相同内容）
- 修复节点配置面板无法滚动到删除按钮的问题
- 修复 Unrealized PnL 显示 -100% 的问题（`mark_price` 为 0 时的处理）
- 修复 Trade History "All bots" 页卡始终为空的问题

#### 后端修复
- 修复交易所类型获取错误：使用 `exchange_cfg['type']` 而非 `exchange_cfg['name']`
- 修复 Batch Decision 结果未写入 `state.debate_decision` 导致前端无法显示
- 修复删除 Bot 后列表不更新的问题（`is_active` 默认过滤）
- 修复 `markPrice` 为 0 时的 API 返回值（fallback 到 `fetch_ticker`）

### 🔧 架构优化 / Architecture Improvements

#### 多进程并发优化
- **PostgreSQL Advisory Lock**: 使用 `pg_try_advisory_lock` 防止多进程同时执行 DDL 操作
- **快速路径检查**: `init_db()` 开头检查核心表是否存在，已初始化则直接返回
- **移除重复初始化**: Bot 子进程不再调用 `init_db()`，由 API 服务启动时统一初始化

#### 工作流保护
- 用户手动编辑的工作流不再被 `PluginAutoSync` 覆盖

#### 持仓价格补全
- `market_state` 节点确保所有持仓的币种都有实时价格（即使不在 `coins_pick` 选出的列表中）

### 📁 文件变更 / Changed Files

| 文件 | 变更内容 |
|------|---------|
| `frontend/*` | 新增完整的 Next.js 前端应用 |
| `docker-compose.yml` | Docker 部署配置 |
| `Dockerfile.api` | API 服务 Docker 镜像 |
| `frontend/Dockerfile` | 前端 Docker 镜像 |
| `packages/langtrader_core/data/database.py` | Advisory Lock + 快速路径检查 |
| `packages/langtrader_core/services/trader.py` | 修复 exchange_name 获取 |
| `packages/langtrader_core/graph/nodes/batch_decision.py` | 写入 debate_decision |
| `packages/langtrader_core/graph/nodes/market_state.py` | 持仓价格补全 |
| `packages/langtrader_core/plugins/auto_sync.py` | 工作流保护 |
| `packages/langtrader_api/routes/v1/bots.py` | 状态徽章 + markPrice 修复 |
| `examples/run_once.py` | 移除 init_db() 调用 |

---

## [0.2.1] - 2026-01-04

### 🐛 Bug 修复 / Bug Fixes

#### AnalystOutput 验证错误修复
- 修复 `debate_decision.py` 中 fallback 返回的 `AnalystOutput` 缺少 `symbol` 字段的问题
- 修复 `key_levels` 字段类型错误（应为 `None` 而非 `[]`）

### ✨ 新增功能 / New Features

#### API 与 Bot 状态同步机制
- **新增 `status_file.py` 服务**: 实现 Bot 运行状态的文件同步
- **Bot 进程状态写入**: 每个交易周期结束后自动写入状态到 `status/bot_{id}.json`
- **API 状态读取**: `GET /api/v1/bots/{id}/status` 现在返回详细运行信息：
  - `cycle`: 当前周期数
  - `balance`: 当前余额
  - `positions_count`: 持仓数量
  - `symbols_trading`: 当前监控的币种
  - `last_decision`: 最后一次决策摘要
  - `state`: 运行状态 (running/error/stopped)
  - `last_error`: 最后一次错误信息

### 📁 文件变更 / Changed Files

| 文件 | 变更内容 |
|------|---------|
| `packages/langtrader_core/graph/nodes/debate_decision.py` | 修复 AnalystOutput fallback |
| `packages/langtrader_core/services/status_file.py` | 新增状态文件服务 |
| `examples/run_once.py` | 添加状态文件写入逻辑 |
| `packages/langtrader_api/services/bot_manager.py` | 添加状态文件读取方法 |
| `packages/langtrader_api/routes/v1/bots.py` | 更新 status 端点使用状态文件 |
| `packages/langtrader_api/schemas/bots.py` | BotStatus 新增字段 |

---

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

