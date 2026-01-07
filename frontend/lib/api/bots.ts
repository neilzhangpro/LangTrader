/**
 * Bot API 模块
 * 提供 Bot 管理相关的所有 API 调用
 */

import { get, post, patch, del } from './client'
import type {
  BotSummary,
  BotDetail,
  BotStatus,
  BotCreateRequest,
  BotUpdateRequest,
  PositionInfo,
  BalanceInfo,
  PaginatedResponse,
} from '@/types/api'

/**
 * 获取 Bot 列表
 */
export async function listBots(params?: {
  page?: number
  page_size?: number
  is_active?: boolean
  trading_mode?: string
}): Promise<PaginatedResponse<BotSummary>> {
  return get('/api/v1/bots', params)
}

/**
 * 获取 Bot 详情
 */
export async function getBot(botId: number): Promise<BotDetail> {
  return get(`/api/v1/bots/${botId}`)
}

/**
 * 创建 Bot
 */
export async function createBot(data: BotCreateRequest): Promise<BotDetail> {
  return post('/api/v1/bots', data)
}

/**
 * 更新 Bot
 */
export async function updateBot(botId: number, data: BotUpdateRequest): Promise<BotDetail> {
  return patch(`/api/v1/bots/${botId}`, data)
}

/**
 * 删除 Bot
 */
export async function deleteBot(botId: number): Promise<void> {
  return del(`/api/v1/bots/${botId}`)
}

/**
 * 获取 Bot 状态
 */
export async function getBotStatus(botId: number): Promise<BotStatus> {
  return get(`/api/v1/bots/${botId}/status`)
}

/**
 * 启动 Bot
 */
export async function startBot(botId: number): Promise<{ bot_id: number; action: string }> {
  return post(`/api/v1/bots/${botId}/start`)
}

/**
 * 停止 Bot
 */
export async function stopBot(botId: number): Promise<{ bot_id: number; action: string }> {
  return post(`/api/v1/bots/${botId}/stop`)
}

/**
 * 重启 Bot
 */
export async function restartBot(botId: number): Promise<{ bot_id: number; action: string }> {
  return post(`/api/v1/bots/${botId}/restart`)
}

/**
 * 获取 Bot 持仓
 */
export async function getBotPositions(botId: number): Promise<PositionInfo[]> {
  return get(`/api/v1/bots/${botId}/positions`)
}

/**
 * 获取 Bot 余额
 */
export async function getBotBalance(botId: number): Promise<BalanceInfo> {
  return get(`/api/v1/bots/${botId}/balance`)
}

/**
 * 获取 Bot 日志
 */
export async function getBotLogs(botId: number, lines?: number): Promise<{
  bot_id: number
  bot_name: string
  lines_requested: number
  logs: string
}> {
  return get(`/api/v1/bots/${botId}/logs`, { lines })
}

// =============================================================================
// AI Debate Types
// =============================================================================

/**
 * 市场分析师输出
 */
export interface AnalystOutput {
  symbol: string
  trend: 'bullish' | 'bearish' | 'neutral'
  key_levels?: Record<string, number>
  summary: string
}

/**
 * 交易员建议 (Bull/Bear)
 */
export interface TraderSuggestion {
  symbol: string
  action: 'long' | 'short' | 'wait'
  confidence: number
  allocation_pct: number
  stop_loss_pct: number
  take_profit_pct: number
  reasoning: string
}

/**
 * 最终投资组合决策
 */
export interface PortfolioDecision {
  symbol: string
  action: string
  allocation_pct: number
  confidence: number
  leverage: number
  stop_loss?: number
  take_profit?: number
  priority: number
  reasoning: string
}

/**
 * 批量决策结果
 */
export interface BatchDecision {
  decisions: PortfolioDecision[]
  total_allocation_pct: number
  cash_reserve_pct: number
  strategy_rationale: string
}

/**
 * AI 辩论结果
 */
export interface DebateResult {
  analyst_outputs: AnalystOutput[]
  bull_suggestions: TraderSuggestion[]
  bear_suggestions: TraderSuggestion[]
  final_decision?: BatchDecision
  debate_summary: string
  completed_at?: string
}

/**
 * 获取 Bot AI 辩论结果
 * 返回完整的辩论过程：分析师分析 -> 多头/空头建议 -> 最终决策
 */
export async function getBotDebate(botId: number): Promise<DebateResult | null> {
  return get(`/api/v1/bots/${botId}/debate`)
}

