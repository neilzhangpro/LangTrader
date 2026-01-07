/**
 * Trades API 模块
 * 提供交易历史相关的 API 调用
 */

import { get } from './client'
import type {
  TradeRecord,
  TradeSummary,
  DailyPerformance,
  PaginatedResponse,
} from '@/types/api'

/**
 * 获取交易列表
 */
export async function listTrades(params?: {
  page?: number
  page_size?: number
  bot_id?: number
  symbol?: string
  status?: 'open' | 'closed'
  side?: 'long' | 'short'
  start_date?: string
  end_date?: string
}): Promise<PaginatedResponse<TradeRecord>> {
  return get('/api/v1/trades', params)
}

/**
 * 获取交易摘要
 */
export async function getTradeSummary(
  botId: number,
  period?: 'day' | 'week' | 'month' | 'all'
): Promise<TradeSummary> {
  return get('/api/v1/trades/summary', { bot_id: botId, period })
}

/**
 * 获取每日绩效
 */
export async function getDailyPerformance(
  botId: number,
  days?: number
): Promise<DailyPerformance[]> {
  return get('/api/v1/trades/daily', { bot_id: botId, days })
}

/**
 * 获取交易详情
 */
export async function getTrade(tradeId: number): Promise<TradeRecord> {
  return get(`/api/v1/trades/${tradeId}`)
}

