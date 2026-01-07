/**
 * API 响应类型定义
 * 与后端 FastAPI schemas 对应
 */

// =============================================================================
// Base Response Types
// =============================================================================

export interface APIResponse<T> {
  success: boolean
  data: T
  message?: string
  timestamp: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ErrorResponse {
  success: boolean
  error: string
  detail?: string
  code: string
  timestamp: string
}

// =============================================================================
// Bot Types
// =============================================================================

export interface BotSummary {
  id: number
  name: string
  display_name?: string
  is_active: boolean
  trading_mode: 'paper' | 'live' | 'backtest'
  exchange_id: number
  workflow_id: number
  created_at: string
  last_active_at?: string
}

export interface BotDetail extends BotSummary {
  description?: string
  prompt?: string
  llm_id?: number
  enable_tracing: boolean
  tracing_project: string
  tracing_key?: string
  tavily_search_key?: string
  max_concurrent_symbols: number
  cycle_interval_seconds: number
  max_leverage: number
  quant_signal_weights?: Record<string, number>
  quant_signal_threshold: number
  risk_limits?: Record<string, unknown>
  // Dynamic config
  trading_timeframes?: string[]
  ohlcv_limits?: Record<string, number>
  indicator_configs?: Record<string, unknown>
  // Balance
  initial_balance?: number
  current_balance?: number
  updated_at: string
  created_by?: string
}

export interface BotStatus {
  bot_id: number
  bot_name: string
  is_running: boolean
  is_active: boolean
  trading_mode: string
  current_cycle: number
  last_cycle_at?: string
  open_positions: number
  symbols_trading: string[]
  uptime_seconds?: number
  error_message?: string
  balance?: number
  initial_balance?: number
  last_decision?: string
  state: 'running' | 'idle' | 'error' | 'stopped' | 'unknown'
}

export interface BotCreateRequest {
  name: string
  display_name?: string
  description?: string
  prompt?: string
  exchange_id: number
  workflow_id: number
  llm_id?: number
  trading_mode?: 'paper' | 'live' | 'backtest'
  // Tracing config
  enable_tracing?: boolean
  tracing_project?: string
  tracing_key?: string
  // Agent search key
  tavily_search_key?: string
  // Trading params
  max_concurrent_symbols?: number
  cycle_interval_seconds?: number
  max_leverage?: number
  quant_signal_weights?: Record<string, number>
  quant_signal_threshold?: number
  risk_limits?: Record<string, unknown>
  // Dynamic config
  trading_timeframes?: string[]
  ohlcv_limits?: Record<string, number>
  indicator_configs?: Record<string, unknown>
  // Balance
  initial_balance?: number
}

export interface BotUpdateRequest {
  display_name?: string
  description?: string
  prompt?: string
  exchange_id?: number
  workflow_id?: number
  llm_id?: number
  is_active?: boolean
  trading_mode?: 'paper' | 'live' | 'backtest'
  // Tracing config
  enable_tracing?: boolean
  tracing_project?: string
  tracing_key?: string
  // Agent search key
  tavily_search_key?: string
  // Trading params
  max_concurrent_symbols?: number
  cycle_interval_seconds?: number
  max_leverage?: number
  quant_signal_weights?: Record<string, number>
  quant_signal_threshold?: number
  risk_limits?: Record<string, unknown>
  // Dynamic config
  trading_timeframes?: string[]
  ohlcv_limits?: Record<string, number>
  indicator_configs?: Record<string, unknown>
  // Balance
  initial_balance?: number
}

// =============================================================================
// Position & Balance Types
// =============================================================================

export interface PositionInfo {
  symbol: string
  side: 'long' | 'short'
  size: number
  entry_price: number
  mark_price: number
  unrealized_pnl: number
  leverage: number
  margin_used: number
  liquidation_price?: number
}

export interface BalanceInfo {
  bot_id: number
  bot_name: string
  exchange_id: number
  total_usd: number
  balances: Record<string, number>
  initial_balance?: number
  current_balance?: number
  pnl_usd?: number
  pnl_percent?: number
  updated_at: string
}

// =============================================================================
// Exchange Types
// =============================================================================

export interface ExchangeSummary {
  id: number
  name: string
  type: string
  testnet: boolean
  has_api_key: boolean
  has_secret_key: boolean
}

export interface ExchangeDetail {
  id: number
  name: string
  type: string
  testnet: boolean
  apikey_masked: string
  has_uid: boolean
  has_password: boolean
  slippage?: number
}

export interface ExchangeCreateRequest {
  name: string
  type: string
  apikey: string
  secretkey: string
  uid?: string
  password?: string
  testnet?: boolean
  slippage?: number
}

export interface ExchangeUpdateRequest {
  name?: string
  type?: string
  apikey?: string
  secretkey?: string
  uid?: string
  password?: string
  testnet?: boolean
  slippage?: number
}

export interface ExchangeTestResult {
  success: boolean
  message: string
  latency_ms?: number
}

export interface ExchangeBalance {
  exchange_id: number
  exchange_name: string
  total_usd: number
  balances: Record<string, number>
  updated_at: string
}

// =============================================================================
// LLM Config Types
// =============================================================================

export interface LLMConfigSummary {
  id: number
  name: string
  display_name?: string
  provider: string
  model_name: string
  is_enabled: boolean
  is_default: boolean
}

export interface LLMConfigDetail extends LLMConfigSummary {
  description?: string
  base_url?: string
  api_key_masked?: string
  temperature: number
  max_retries: number
  created_at: string
  updated_at: string
}

export interface LLMConfigCreateRequest {
  name: string
  display_name?: string
  description?: string
  provider: string
  model_name: string
  base_url?: string
  api_key?: string
  temperature?: number
  max_retries?: number
  is_enabled?: boolean
}

export interface LLMConfigUpdateRequest {
  display_name?: string
  description?: string
  provider?: string
  model_name?: string
  base_url?: string
  api_key?: string
  temperature?: number
  max_retries?: number
  is_enabled?: boolean
}

export interface LLMConfigTestResult {
  success: boolean
  message: string
  response_preview?: string
  latency_ms?: number
}

// =============================================================================
// Workflow Types
// =============================================================================

export interface WorkflowSummary {
  id: number
  name: string
  display_name?: string
  version: string
  category: string
  is_active: boolean
  nodes_count: number
  edges_count: number
}

export interface WorkflowDetail extends WorkflowSummary {
  description?: string
  created_at?: string
  updated_at?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
}

export interface WorkflowNode {
  id: number
  name: string
  plugin_name: string
  display_name?: string
  description?: string
  enabled: boolean
  execution_order: number
  config?: Record<string, unknown>
  // 插件元数据（从后端增强返回）
  category?: string
  requires_llm?: boolean
  requires_trader?: boolean
}

export interface WorkflowEdge {
  id: number
  from_node: string
  to_node: string
  condition?: string
}

export interface PluginInfo {
  name: string
  display_name: string
  version: string
  author: string
  description: string
  category: string
  requires_trader: boolean
  requires_llm: boolean
  insert_after?: string
  suggested_order: number
}

// =============================================================================
// Performance Types
// =============================================================================

export interface PerformanceMetrics {
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  avg_return_pct: number
  total_return_usd: number
  sharpe_ratio: number
  max_drawdown: number
  profit_factor: number
  avg_win_pct: number
  avg_loss_pct: number
}

// =============================================================================
// Trade Types
// =============================================================================

export interface TradeRecord {
  id: number
  bot_id: number
  symbol: string
  side: 'long' | 'short'
  action: string
  entry_price?: number
  exit_price?: number
  amount: number
  leverage: number
  pnl_usd?: number
  pnl_percent?: number
  fee_paid?: number
  status: 'open' | 'closed'
  opened_at: string
  closed_at?: string
  cycle_id?: string
  order_id?: string
}

export interface TradeSummary {
  bot_id: number
  period: string
  total_trades: number
  winning_trades: number
  losing_trades: number
  open_trades: number
  total_pnl_usd: number
  total_fees_usd: number
  net_pnl_usd: number
  best_trade_pnl: number
  worst_trade_pnl: number
  avg_trade_pnl: number
  symbols_traded: string[]
}

export interface DailyPerformance {
  date: string
  bot_id: number
  trades: number
  winning_trades: number
  losing_trades: number
  pnl_usd: number
  pnl_percent: number
  fees_usd: number
  symbols: string[]
}

// =============================================================================
// Health Types
// =============================================================================

export interface HealthResponse {
  status: string
  version: string
  environment: string
  database: string
  timestamp: string
}

