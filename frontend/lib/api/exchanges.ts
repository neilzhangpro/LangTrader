/**
 * Exchange API 模块
 * 提供交易所配置管理相关的 API 调用
 */

import { get, post, patch, del } from './client'
import type {
  ExchangeSummary,
  ExchangeDetail,
  ExchangeCreateRequest,
  ExchangeUpdateRequest,
  ExchangeTestResult,
  ExchangeBalance,
} from '@/types/api'

/**
 * 获取交易所列表
 */
export async function listExchanges(): Promise<ExchangeSummary[]> {
  return get('/api/v1/exchanges')
}

/**
 * 获取交易所详情
 */
export async function getExchange(exchangeId: number): Promise<ExchangeDetail> {
  return get(`/api/v1/exchanges/${exchangeId}`)
}

/**
 * 创建交易所配置
 */
export async function createExchange(data: ExchangeCreateRequest): Promise<ExchangeDetail> {
  return post('/api/v1/exchanges', data)
}

/**
 * 更新交易所配置
 */
export async function updateExchange(
  exchangeId: number,
  data: ExchangeUpdateRequest
): Promise<ExchangeDetail> {
  return patch(`/api/v1/exchanges/${exchangeId}`, data)
}

/**
 * 删除交易所配置
 */
export async function deleteExchange(exchangeId: number): Promise<void> {
  return del(`/api/v1/exchanges/${exchangeId}`)
}

/**
 * 测试交易所连接
 */
export async function testExchange(exchangeId: number): Promise<ExchangeTestResult> {
  return post(`/api/v1/exchanges/${exchangeId}/test`)
}

/**
 * 获取交易所余额
 */
export async function getExchangeBalance(exchangeId: number): Promise<ExchangeBalance> {
  return get(`/api/v1/exchanges/${exchangeId}/balance`)
}

