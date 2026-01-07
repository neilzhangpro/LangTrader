'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { GitBranch, Plug, ChevronRight, Eye, EyeOff, Edit, Plus, Trash2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { WorkflowCanvas } from '@/components/workflows/workflow-canvas'
import { CreateWorkflowDialog } from '@/components/workflows/create-workflow-dialog'
import { toast } from '@/components/ui/use-toast'
import * as workflowsApi from '@/lib/api/workflows'

/**
 * 工作流配置页面
 * 支持查看工作流列表、可视化画布、插件列表、创建和删除工作流
 */
export default function WorkflowsPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  // 选中的工作流 ID（用于显示可视化）
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<number | null>(null)

  // 获取工作流列表
  const { data: workflows, isLoading: isLoadingWorkflows } = useQuery({
    queryKey: ['workflows'],
    queryFn: workflowsApi.listWorkflows,
  })

  // 获取选中工作流的详情（包含 nodes 和 edges）- 禁用缓存确保数据准确
  const { data: workflowDetail, isLoading: isLoadingDetail } = useQuery({
    queryKey: ['workflow', selectedWorkflowId],
    queryFn: () => workflowsApi.getWorkflow(selectedWorkflowId!),
    enabled: !!selectedWorkflowId,
    staleTime: 0,  // 数据立即过期
    refetchOnMount: 'always',  // 始终刷新
  })

  // 获取插件列表
  const { data: plugins, isLoading: isLoadingPlugins } = useQuery({
    queryKey: ['plugins'],
    queryFn: workflowsApi.listPlugins,
  })

  // 删除 workflow mutation
  const deleteMutation = useMutation({
    mutationFn: (workflowId: number) => workflowsApi.deleteWorkflow(workflowId),
    onSuccess: () => {
      toast({
        title: 'Workflow Deleted',
        description: 'The workflow has been deleted successfully.',
      })
      queryClient.invalidateQueries({ queryKey: ['workflows'] })
      // 如果删除的是当前选中的，清除选中状态
      setSelectedWorkflowId(null)
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to delete workflow',
        variant: 'destructive',
      })
    },
  })

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
      <div>
        <h1 className="text-3xl font-bold">Workflows</h1>
        <p className="text-muted-foreground">
            View and manage trading workflows
        </p>
        </div>
        <CreateWorkflowDialog>
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Create Workflow
          </Button>
        </CreateWorkflowDialog>
      </div>

      {/* 工作流列表 */}
      <div>
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <GitBranch className="h-5 w-5" />
          Available Workflows
        </h2>
        
        {isLoadingWorkflows ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2].map((i) => (
              <Card key={i} className="h-32 animate-pulse bg-muted" />
            ))}
          </div>
        ) : workflows && workflows.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {workflows.map((workflow) => (
              <Card 
                key={workflow.id}
                className={`cursor-pointer transition-all hover:shadow-md ${
                  selectedWorkflowId === workflow.id 
                    ? 'ring-2 ring-primary' 
                    : ''
                }`}
                onClick={() => setSelectedWorkflowId(
                  selectedWorkflowId === workflow.id ? null : workflow.id
                )}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2 text-lg">
                        {workflow.display_name || workflow.name}
                      </CardTitle>
                      <CardDescription className="mt-1">
                        v{workflow.version} • {workflow.category}
                      </CardDescription>
                    </div>
                    <Badge variant={workflow.is_active ? 'default' : 'secondary'}>
                      {workflow.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span>{workflow.nodes_count} nodes</span>
                      <span>{workflow.edges_count} edges</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button 
                        variant="ghost" 
                        size="sm"
                        className="gap-1"
                      >
                        {selectedWorkflowId === workflow.id ? (
                          <>
                            <EyeOff className="h-4 w-4" />
                            Hide
                          </>
                        ) : (
                          <>
                            <Eye className="h-4 w-4" />
                            View
                          </>
                        )}
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm"
                        className="gap-1"
                        onClick={(e) => {
                          e.stopPropagation()
                          router.push(`/settings/workflows/${workflow.id}/edit`)
                        }}
                      >
                        <Edit className="h-4 w-4" />
                        Edit
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button 
                            variant="outline" 
                            size="sm"
                            className="gap-1 text-destructive hover:text-destructive"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent onClick={(e) => e.stopPropagation()}>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Delete Workflow</AlertDialogTitle>
                            <AlertDialogDescription>
                              Are you sure you want to delete &quot;{workflow.display_name || workflow.name}&quot;?
                              This action cannot be undone. All nodes and edges will be permanently removed.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              onClick={() => deleteMutation.mutate(workflow.id)}
                            >
                              {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="p-8 text-center">
            <GitBranch className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground mb-4">No workflows found</p>
            <CreateWorkflowDialog>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Create Your First Workflow
              </Button>
            </CreateWorkflowDialog>
          </Card>
        )}
      </div>

      {/* 工作流可视化画布 */}
      {selectedWorkflowId && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold flex items-center gap-2">
              <Eye className="h-5 w-5" />
              Workflow Visualization
              {workflowDetail && (
                <Badge variant="outline" className="ml-2">
                  {workflowDetail.display_name || workflowDetail.name}
                </Badge>
              )}
            </h2>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => setSelectedWorkflowId(null)}
            >
              Close
            </Button>
          </div>
          
          {isLoadingDetail ? (
            <Card className="h-[500px] animate-pulse bg-muted" />
          ) : workflowDetail ? (
            <WorkflowCanvas
              nodes={workflowDetail.nodes}
              edges={workflowDetail.edges}
            />
          ) : (
            <Card className="h-[500px] flex items-center justify-center">
              <p className="text-muted-foreground">Failed to load workflow</p>
            </Card>
          )}
          
          {/* 节点列表 */}
          {workflowDetail && workflowDetail.nodes.length > 0 && (
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {workflowDetail.nodes.map((node) => (
                <Card key={node.id} className="p-3">
                  <div className="flex items-center gap-3">
                    <div 
                      className="w-3 h-3 rounded-full"
                      style={{ 
                        backgroundColor: node.enabled ? '#22c55e' : '#94a3b8' 
                      }}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">
                        {node.display_name || node.name}
                      </div>
                      <div className="text-xs text-muted-foreground truncate">
                        {node.plugin_name}
                      </div>
                    </div>
                    <Badge variant="outline" className="text-xs">
                      #{node.execution_order}
                    </Badge>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 插件列表 */}
      <div>
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Plug className="h-5 w-5" />
          Available Plugins
        </h2>
        
        {isLoadingPlugins ? (
          <div className="space-y-2">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i} className="h-16 animate-pulse bg-muted" />
            ))}
          </div>
        ) : plugins && plugins.length > 0 ? (
          <div className="space-y-2">
            {plugins.map((plugin) => (
              <Card key={plugin.name} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Plug className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <h3 className="font-medium">{plugin.display_name}</h3>
                      <p className="text-sm text-muted-foreground">
                        {plugin.description}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      v{plugin.version} by {plugin.author}
                    </span>
                    <Badge variant="outline">{plugin.category}</Badge>
                    {plugin.requires_llm && (
                      <Badge variant="secondary">Requires LLM</Badge>
                    )}
                    {plugin.requires_trader && (
                      <Badge variant="secondary">Requires Trader</Badge>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <Card className="p-8 text-center">
            <Plug className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <p className="text-muted-foreground">No plugins found</p>
          </Card>
        )}
      </div>
    </div>
  )
}
