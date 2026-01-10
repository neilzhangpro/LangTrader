'use client'

import { useCallback, useMemo, useState, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  addEdge,
  MarkerType,
  Position,
  type Node,
  type Edge,
  type Connection,
  type OnNodesChange,
  type OnEdgesChange,
  ReactFlowProvider,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { Save, Undo2, Redo2, LayoutGrid, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useToast } from '@/components/ui/use-toast'

import { WorkflowNode } from './workflow-node'
import { PluginLibrary, type PluginInfo } from './plugin-library'
import { NodeConfigPanel } from './node-config-panel'

// 节点类别颜色
const CATEGORY_COLORS: Record<string, string> = {
  data_source: '#3b82f6',
  analysis: '#8b5cf6',
  decision: '#f59e0b',
  execution: '#10b981',
  monitoring: '#6366f1',
  Basic: '#64748b',
  general: '#64748b',
}

export interface WorkflowNodeData {
  id: number
  name: string
  plugin_name: string
  enabled: boolean
  execution_order: number
  category?: string
  display_name?: string
  description?: string
  requires_llm?: boolean
  requires_trader?: boolean
  config?: Record<string, unknown>
}

export interface WorkflowEdgeData {
  id: number
  from_node: string
  to_node: string
  condition?: string | null
}

interface WorkflowEditorProps {
  workflowId: number
  workflowName: string
  initialNodes: WorkflowNodeData[]
  initialEdges: WorkflowEdgeData[]
  availablePlugins: PluginInfo[]
  onSave: (nodes: Node[], edges: Edge[]) => Promise<void>
  className?: string
}

let nodeId = 100 // 临时 ID 计数器

/**
 * 可编辑的工作流编辑器
 * 支持拖拽添加节点、连接节点、删除节点等操作
 */
export function WorkflowEditor({
  workflowId,
  workflowName,
  initialNodes: dbNodes,
  initialEdges: dbEdges,
  availablePlugins,
  onSave,
  className,
}: WorkflowEditorProps) {
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { toast } = useToast()
  
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)

  // 转换数据库节点为 React Flow 格式
  const convertToFlowNodes = useCallback((dbNodes: WorkflowNodeData[]): Node[] => {
    const sortedNodes = [...dbNodes].sort((a, b) => a.execution_order - b.execution_order)
    const nodeSpacingX = 280
    const startX = 150
    const startY = 200

    const flowNodes: Node[] = [
      {
        id: 'START',
        type: 'input',
        position: { x: startX - 130, y: startY },
        data: { label: '🚀 START' },
        deletable: false,
        style: {
          background: '#22c55e',
          color: 'white',
          border: 'none',
          borderRadius: '50%',
          width: 80,
          height: 80,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '14px',
          fontWeight: 'bold',
        },
      },
    ]

    sortedNodes.forEach((node, index) => {
      const category = node.category || 'general'
      const color = CATEGORY_COLORS[category] || CATEGORY_COLORS.general

      flowNodes.push({
        id: node.name,
        type: 'workflow',
        position: {
          x: startX + index * nodeSpacingX,
          y: startY - 30 + (index % 2) * 60,
        },
        data: {
          label: node.display_name || node.name,
          name: node.name,
          pluginName: node.plugin_name,
          enabled: node.enabled,
          category,
          color,
          description: node.description,
          requiresLlm: node.requires_llm,
          requiresTrader: node.requires_trader,
          executionOrder: node.execution_order,
          config: node.config || {},  // 包含节点配置
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      })
    })

    flowNodes.push({
      id: 'END',
      type: 'output',
      position: {
        x: startX + sortedNodes.length * nodeSpacingX,
        y: startY,
      },
      data: { label: '🏁 END' },
      deletable: false,
      style: {
        background: '#ef4444',
        color: 'white',
        border: 'none',
        borderRadius: '50%',
        width: 80,
        height: 80,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: '14px',
        fontWeight: 'bold',
      },
    })

    return flowNodes
  }, [])

  // 转换数据库边为 React Flow 格式
  const convertToFlowEdges = useCallback((dbEdges: WorkflowEdgeData[]): Edge[] => {
    return dbEdges.map((edge) => ({
      id: `e-${edge.from_node}-${edge.to_node}`,
      source: edge.from_node,
      target: edge.to_node,
      label: edge.condition || undefined,
      type: 'smoothstep',
      animated: !!edge.condition,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edge.condition ? '#f59e0b' : '#64748b',
      },
      style: {
        stroke: edge.condition ? '#f59e0b' : '#64748b',
        strokeWidth: 2,
      },
    }))
  }, [])

  const [nodes, setNodes, onNodesChange] = useNodesState(convertToFlowNodes(dbNodes))
  const [edges, setEdges, onEdgesChange] = useEdgesState(convertToFlowEdges(dbEdges))

  // 节点类型映射
  const nodeTypes = useMemo(() => ({ workflow: WorkflowNode }), [])

  // 监听变化
  const handleNodesChange: OnNodesChange = useCallback(
    (changes) => {
      onNodesChange(changes)
      setHasChanges(true)
    },
    [onNodesChange]
  )

  const handleEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      onEdgesChange(changes)
      setHasChanges(true)
    },
    [onEdgesChange]
  )

  // 连接节点
  const onConnect = useCallback(
    (params: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            type: 'smoothstep',
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: '#64748b',
            },
            style: {
              stroke: '#64748b',
              strokeWidth: 2,
            },
          },
          eds
        )
      )
      setHasChanges(true)
    },
    [setEdges]
  )

  // 点击节点
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    // 只对工作流节点显示配置面板
    if (node.type === 'workflow') {
      setSelectedNode(node)
    }
  }, [])

  // 拖拽放置
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()

      const data = event.dataTransfer.getData('application/reactflow')
      if (!data) return

      const plugin: PluginInfo = JSON.parse(data)
      
      // 获取放置位置
      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect()
      if (!reactFlowBounds) return

      const position = {
        x: event.clientX - reactFlowBounds.left - 100,
        y: event.clientY - reactFlowBounds.top - 40,
      }

      // 计算新节点的执行顺序
      const workflowNodes = nodes.filter(n => n.type === 'workflow')
      const maxOrder = workflowNodes.reduce((max: number, n) => {
        const order = Number(n.data?.executionOrder) || 0
        return order > max ? order : max
      }, 0)

      const category = plugin.category || 'general'
      const color = CATEGORY_COLORS[category] || CATEGORY_COLORS.general

      const newNode: Node = {
        id: `${plugin.name}_${nodeId++}`,
        type: 'workflow',
        position,
        data: {
          label: plugin.display_name,
          name: plugin.name,
          pluginName: plugin.name,
          enabled: true,
          category,
          color,
          description: plugin.description,
          requiresLlm: plugin.requires_llm,
          requiresTrader: plugin.requires_trader,
          executionOrder: maxOrder + 1,
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      }

      setNodes((nds) => nds.concat(newNode))
      setHasChanges(true)

      toast({
        title: '节点已添加',
        description: `已添加 ${plugin.display_name} 节点`,
      })
    },
    [nodes, setNodes, toast]
  )

  // 更新节点
  const handleUpdateNode = useCallback(
    (nodeId: string, updates: Partial<Node['data']>) => {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.id === nodeId) {
            return {
              ...node,
              data: { ...node.data, ...updates },
            }
          }
          return node
        })
      )
      setHasChanges(true)
      
      // 更新选中节点状态
      if (selectedNode?.id === nodeId) {
        setSelectedNode((prev) =>
          prev ? { ...prev, data: { ...prev.data, ...updates } } : null
        )
      }
    },
    [setNodes, selectedNode]
  )

  // 删除节点
  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((node) => node.id !== nodeId))
      setEdges((eds) =>
        eds.filter((edge) => edge.source !== nodeId && edge.target !== nodeId)
      )
      setHasChanges(true)
      
      toast({
        title: '节点已删除',
        variant: 'destructive',
      })
    },
    [setNodes, setEdges, toast]
  )

  // 保存工作流
  const handleSave = async () => {
    setIsSaving(true)
    try {
      await onSave(nodes, edges)
      setHasChanges(false)
      toast({
        title: '保存成功',
        description: '工作流配置已保存',
      })
    } catch (error) {
      toast({
        title: '保存失败',
        description: String(error),
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  // 自动布局
  const handleAutoLayout = useCallback(() => {
    const workflowNodes = nodes.filter(n => n.type === 'workflow')
    const sortedNodes = [...workflowNodes].sort((a, b) => {
      const orderA = Number(a.data?.executionOrder) || 0
      const orderB = Number(b.data?.executionOrder) || 0
      return orderA - orderB
    })

    const nodeSpacingX = 280
    const startX = 150
    const startY = 200

    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === 'START') {
          return { ...node, position: { x: startX - 130, y: startY } }
        }
        if (node.id === 'END') {
          return { ...node, position: { x: startX + sortedNodes.length * nodeSpacingX, y: startY } }
        }
        const index = sortedNodes.findIndex(n => n.id === node.id)
        if (index >= 0) {
          return {
            ...node,
            position: {
              x: startX + index * nodeSpacingX,
              y: startY - 30 + (index % 2) * 60,
            },
          }
        }
        return node
      })
    )
    setHasChanges(true)
  }, [nodes, setNodes])

  return (
    <div className={`flex h-full ${className || ''}`}>
      {/* 左侧插件库 */}
      <PluginLibrary plugins={availablePlugins} />

      {/* 中间画布 */}
      <div className="flex-1 relative" ref={reactFlowWrapper}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onDragOver={onDragOver}
          onDrop={onDrop}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          snapToGrid
          snapGrid={[15, 15]}
          deleteKeyCode={['Backspace', 'Delete']}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#94a3b8" gap={20} size={1} />
          <Controls className="bg-white dark:bg-slate-800" />
          <MiniMap
            nodeStrokeWidth={3}
            className="bg-white dark:bg-slate-800"
          />

          {/* 顶部工具栏 */}
          <Panel position="top-left" className="flex items-center gap-2 bg-white dark:bg-slate-800 p-2 rounded-lg shadow">
            <span className="text-sm font-medium px-2">
              {workflowName}
            </span>
            {hasChanges && (
              <span className="text-xs text-amber-500 px-2">
                (未保存)
              </span>
            )}
          </Panel>

          <Panel position="top-right" className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleAutoLayout}
              title="自动布局"
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={!hasChanges || isSaving}
            >
              <Save className="h-4 w-4 mr-1" />
              {isSaving ? '保存中...' : '保存'}
            </Button>
          </Panel>
        </ReactFlow>
      </div>

      {/* 右侧配置面板 */}
      <NodeConfigPanel
        node={selectedNode}
        onClose={() => setSelectedNode(null)}
        onUpdate={handleUpdateNode}
        onDelete={handleDeleteNode}
      />
    </div>
  )
}

/**
 * 包装组件（提供 ReactFlowProvider）
 */
export function WorkflowEditorWrapper(props: WorkflowEditorProps) {
  return (
    <ReactFlowProvider>
      <WorkflowEditor {...props} />
    </ReactFlowProvider>
  )
}

