'use client'

import { useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { WorkflowEditorWrapper } from '@/components/workflows/workflow-editor'
import * as workflowsApi from '@/lib/api/workflows'
import type { Node, Edge } from '@xyflow/react'

/**
 * 工作流可视化编辑页面
 */
export default function WorkflowEditPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const workflowId = Number(params.id)

  // 进入页面时清除可能存在的旧缓存，确保获取正确的 workflow 数据
  useEffect(() => {
    queryClient.removeQueries({ queryKey: ['workflow', workflowId] })
  }, [workflowId, queryClient])

  // 获取工作流详情 - 完全禁用缓存确保每次获取最新数据
  const { data: workflow, isLoading: isLoadingWorkflow, error: workflowError } = useQuery({
    queryKey: ['workflow', workflowId],
    queryFn: () => workflowsApi.getWorkflow(workflowId),
    enabled: !!workflowId,
    staleTime: 0,  // 数据立即过期
    gcTime: 0,  // 禁用缓存垃圾回收
    refetchOnMount: 'always',  // 组件挂载时始终刷新
  })

  // 获取可用插件
  const { data: plugins, isLoading: isLoadingPlugins } = useQuery({
    queryKey: ['plugins'],
    queryFn: workflowsApi.listPlugins,
  })

  // 保存工作流
  const saveMutation = useMutation({
    mutationFn: async ({ nodes, edges }: { nodes: Node[], edges: Edge[] }) => {
      // 过滤掉 START 和 END 节点
      const workflowNodes = nodes
        .filter(n => n.type === 'workflow')
        .map((n, index) => ({
          name: String(n.data?.name || n.id),
          plugin_name: String(n.data?.pluginName || ''),
          display_name: String(n.data?.label || ''),
          enabled: Boolean(n.data?.enabled),
          execution_order: Number(n.data?.executionOrder) || index + 1,
        }))

      // 转换边
      const workflowEdges = edges.map(e => ({
        from_node: e.source,
        to_node: e.target,
        condition: typeof e.label === 'string' ? e.label : null,
      }))

      await workflowsApi.updateWorkflow(workflowId, {
        nodes: workflowNodes,
        edges: workflowEdges,
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workflow', workflowId] })
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
    },
  })

  const handleSave = async (nodes: Node[], edges: Edge[]) => {
    await saveMutation.mutateAsync({ nodes, edges })
  }

  const isLoading = isLoadingWorkflow || isLoadingPlugins

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-200px)]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (workflowError || !workflow) {
    return (
      <div className="flex flex-col items-center justify-center h-[calc(100vh-200px)] gap-4">
        <p className="text-muted-foreground">工作流加载失败</p>
        <Button variant="outline" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          返回
        </Button>
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-100px)] flex flex-col">
      {/* 顶部导航 */}
      <div className="flex items-center gap-4 p-4 border-b">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-1" />
          返回
        </Button>
        <div>
          <h1 className="text-lg font-semibold">编辑工作流</h1>
          <p className="text-sm text-muted-foreground">
            {workflow.display_name || workflow.name}
          </p>
        </div>
      </div>

      {/* 编辑器 - 使用 workflowId 作为 key 确保不同 workflow 触发重新挂载 */}
      <div className="flex-1">
        <WorkflowEditorWrapper
          key={`workflow-editor-${workflowId}`}
          workflowId={workflowId}
          workflowName={workflow.display_name || workflow.name}
          initialNodes={workflow.nodes || []}
          initialEdges={workflow.edges || []}
          availablePlugins={plugins || []}
          onSave={handleSave}
        />
      </div>
    </div>
  )
}

