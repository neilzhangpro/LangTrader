import { get, post, put, del } from './client'
import type { WorkflowSummary, WorkflowDetail, PluginInfo } from '@/types/api'

/**
 * 获取工作流列表
 */
export async function listWorkflows(): Promise<WorkflowSummary[]> {
  return get<WorkflowSummary[]>('/api/v1/workflows')
}

/**
 * 获取工作流详情
 */
export async function getWorkflow(workflowId: number): Promise<WorkflowDetail> {
  return get<WorkflowDetail>(`/api/v1/workflows/${workflowId}`)
}

/**
 * 获取可用插件列表
 */
export async function listPlugins(): Promise<PluginInfo[]> {
  return get<PluginInfo[]>('/api/v1/workflows/plugins')
}

/**
 * 更新工作流节点和边
 */
export interface UpdateWorkflowRequest {
  nodes: {
    name: string
    plugin_name: string
    display_name?: string
    enabled: boolean
    execution_order: number
  }[]
  edges: {
    from_node: string
    to_node: string
    condition?: string | null
  }[]
}

export async function updateWorkflow(
  workflowId: number,
  data: UpdateWorkflowRequest
): Promise<void> {
  await put(`/api/v1/workflows/${workflowId}`, data)
}

/**
 * 创建新工作流
 */
export interface CreateWorkflowRequest {
  name: string
  display_name?: string
  description?: string
  category?: string
}

export async function createWorkflow(data: CreateWorkflowRequest): Promise<WorkflowSummary> {
  return post<WorkflowSummary>('/api/v1/workflows', data)
}

/**
 * 删除工作流
 */
export async function deleteWorkflow(workflowId: number): Promise<void> {
  await del(`/api/v1/workflows/${workflowId}`)
}
