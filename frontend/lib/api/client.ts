/**
 * API 客户端基础模块
 * 提供统一的请求封装和错误处理
 */

import type { APIResponse, ErrorResponse } from '@/types/api'

// API 基础 URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 默认 API Key（开发环境）
const DEFAULT_API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-key-123'

/**
 * API 错误类
 */
export class APIError extends Error {
  public statusCode: number
  public code: string
  public detail?: string

  constructor(message: string, statusCode: number, code: string, detail?: string) {
    super(message)
    this.name = 'APIError'
    this.statusCode = statusCode
    this.code = code
    this.detail = detail
  }
}

/**
 * 请求配置
 */
interface RequestConfig extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>
}

/**
 * 构建完整的请求 URL
 */
function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(`${API_BASE_URL}${path}`)
  
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        url.searchParams.append(key, String(value))
      }
    })
  }
  
  return url.toString()
}

/**
 * 统一的 API 请求方法
 */
async function request<T>(
  path: string,
  config: RequestConfig = {}
): Promise<T> {
  const { params, ...fetchConfig } = config

  const url = buildUrl(path, params)
  
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    'X-API-Key': DEFAULT_API_KEY,
    ...fetchConfig.headers,
  }

  try {
    const response = await fetch(url, {
      ...fetchConfig,
      headers,
    })

    // 处理 204 No Content
    if (response.status === 204) {
      return null as T
    }

    const data = await response.json()

    if (!response.ok) {
      const errorData = data as ErrorResponse
      throw new APIError(
        errorData.error || 'Request failed',
        response.status,
        errorData.code || `HTTP_${response.status}`,
        errorData.detail
      )
    }

    // 提取 data 字段（APIResponse 包装）
    if ('data' in data && 'success' in data) {
      return (data as APIResponse<T>).data
    }

    return data as T
  } catch (error) {
    if (error instanceof APIError) {
      throw error
    }
    
    // 网络错误
    throw new APIError(
      error instanceof Error ? error.message : 'Network error',
      0,
      'NETWORK_ERROR'
    )
  }
}

/**
 * GET 请求
 */
export async function get<T>(
  path: string,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> {
  return request<T>(path, { method: 'GET', params })
}

/**
 * POST 请求
 */
export async function post<T>(
  path: string,
  body?: unknown,
  params?: Record<string, string | number | boolean | undefined>
): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body ? JSON.stringify(body) : undefined,
    params,
  })
}

/**
 * PATCH 请求
 */
export async function patch<T>(
  path: string,
  body?: unknown
): Promise<T> {
  return request<T>(path, {
    method: 'PATCH',
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * PUT 请求
 */
export async function put<T>(
  path: string,
  body?: unknown
): Promise<T> {
  return request<T>(path, {
    method: 'PUT',
    body: body ? JSON.stringify(body) : undefined,
  })
}

/**
 * DELETE 请求
 */
export async function del<T = void>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}

export { API_BASE_URL }

