/**
 * System Config API 模块
 * 提供系统配置管理相关的 API 调用
 */

import { get, post, put, del } from './client'

// ============ 类型定义 ============

export interface SystemConfig {
  id: number
  config_key: string
  config_value: string
  value_type: 'string' | 'integer' | 'float' | 'boolean' | 'json'
  category: string | null
  description: string | null
  is_editable: boolean
  updated_at: string | null
  updated_by: string | null
}

export interface SystemConfigCreate {
  config_key: string
  config_value: string
  value_type?: 'string' | 'integer' | 'float' | 'boolean' | 'json'
  category?: string
  description?: string
  is_editable?: boolean
}

export interface SystemConfigUpdate {
  config_value?: string
  value_type?: string
  category?: string
  description?: string
  is_editable?: boolean
}

export interface SystemConfigBulkCreate {
  configs: SystemConfigCreate[]
}

// ============ API 方法 ============

/**
 * 获取系统配置列表
 */
export async function listSystemConfigs(params?: {
  category?: string
  prefix?: string
}): Promise<SystemConfig[]> {
  return get('/api/v1/system-configs', params)
}

/**
 * 获取所有配置类别
 */
export async function listCategories(): Promise<string[]> {
  return get('/api/v1/system-configs/categories')
}

/**
 * 获取单个配置
 */
export async function getSystemConfig(configId: number): Promise<SystemConfig> {
  return get(`/api/v1/system-configs/${configId}`)
}

/**
 * 通过 key 获取配置
 */
export async function getSystemConfigByKey(configKey: string): Promise<SystemConfig> {
  return get(`/api/v1/system-configs/key/${configKey}`)
}

/**
 * 创建配置
 */
export async function createSystemConfig(data: SystemConfigCreate): Promise<SystemConfig> {
  return post('/api/v1/system-configs', data)
}

/**
 * 批量创建/更新配置
 */
export async function bulkCreateSystemConfigs(data: SystemConfigBulkCreate): Promise<SystemConfig[]> {
  return post('/api/v1/system-configs/bulk', data)
}

/**
 * 更新配置
 */
export async function updateSystemConfig(
  configId: number,
  data: SystemConfigUpdate
): Promise<SystemConfig> {
  return put(`/api/v1/system-configs/${configId}`, data)
}

/**
 * 删除配置
 */
export async function deleteSystemConfig(configId: number): Promise<void> {
  return del(`/api/v1/system-configs/${configId}`)
}

/**
 * 通过 key 删除配置
 */
export async function deleteSystemConfigByKey(configKey: string): Promise<void> {
  return del(`/api/v1/system-configs/key/${configKey}`)
}

