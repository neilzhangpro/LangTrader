/**
 * Performance API 模块
 * 提供性能指标相关的 API 调用
 */

import { get } from './client'
import type { PerformanceMetrics } from '@/types/api'

/**
 * 获取 Bot 性能指标
 */
export async function getBotPerformance(
  botId: number,
  window?: number
): Promise<PerformanceMetrics> {
  return get(`/api/v1/performance/${botId}`, { window })
}

/**
 * 获取最近交易摘要
 */
export async function getRecentTradesSummary(
  botId: number,
  limit?: number
): Promise<{
  bot_id: number
  limit: number
  summary: string
}> {
  return get(`/api/v1/performance/${botId}/recent`, { limit })
}

/**
 * 比较多个 Bot 的性能
 */
export async function compareBotsPerformance(
  botIds: number[],
  window?: number
): Promise<{
  bots: Record<number, {
    name?: string
    win_rate?: number
    sharpe_ratio?: number
    total_return_usd?: number
    total_trades?: number
    max_drawdown?: number
    error?: string
  }>
  window: number
}> {
  return get('/api/v1/performance/compare', {
    bot_ids: botIds.join(','),
    window,
  })
}

