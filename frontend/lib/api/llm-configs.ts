/**
 * LLM Config API 模块
 * 提供 LLM 配置管理相关的 API 调用
 */

import { get, post, patch, del } from './client'
import type {
  LLMConfigSummary,
  LLMConfigDetail,
  LLMConfigCreateRequest,
  LLMConfigUpdateRequest,
  LLMConfigTestResult,
} from '@/types/api'

/**
 * 获取 LLM 配置列表
 */
export async function listLLMConfigs(enabledOnly?: boolean): Promise<LLMConfigSummary[]> {
  return get('/api/v1/llm-configs', { enabled_only: enabledOnly })
}

/**
 * 获取默认 LLM 配置
 */
export async function getDefaultLLMConfig(): Promise<LLMConfigDetail> {
  return get('/api/v1/llm-configs/default')
}

/**
 * 获取 LLM 配置详情
 */
export async function getLLMConfig(configId: number): Promise<LLMConfigDetail> {
  return get(`/api/v1/llm-configs/${configId}`)
}

/**
 * 创建 LLM 配置
 */
export async function createLLMConfig(data: LLMConfigCreateRequest): Promise<LLMConfigDetail> {
  return post('/api/v1/llm-configs', data)
}

/**
 * 更新 LLM 配置
 */
export async function updateLLMConfig(
  configId: number,
  data: LLMConfigUpdateRequest
): Promise<LLMConfigDetail> {
  return patch(`/api/v1/llm-configs/${configId}`, data)
}

/**
 * 删除 LLM 配置
 */
export async function deleteLLMConfig(configId: number): Promise<void> {
  return del(`/api/v1/llm-configs/${configId}`)
}

/**
 * 设置为默认 LLM 配置
 */
export async function setDefaultLLMConfig(configId: number): Promise<{
  config_id: number
  is_default: boolean
}> {
  return post(`/api/v1/llm-configs/${configId}/set-default`)
}

/**
 * 测试 LLM 配置连接
 */
export async function testLLMConfig(configId: number): Promise<LLMConfigTestResult> {
  return post(`/api/v1/llm-configs/${configId}/test`)
}

