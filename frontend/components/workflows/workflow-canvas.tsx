'use client'

import { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  Position,
  type Node,
  type Edge,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { WorkflowNode } from './workflow-node'

// 节点类别颜色
const CATEGORY_COLORS: Record<string, string> = {
  data_source: '#3b82f6',   // blue
  analysis: '#8b5cf6',      // purple
  decision: '#f59e0b',      // amber
  execution: '#10b981',     // green
  monitoring: '#6366f1',    // indigo
  general: '#64748b',       // slate
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

interface WorkflowCanvasProps {
  nodes: WorkflowNodeData[]
  edges: WorkflowEdgeData[]
  className?: string
}

/**
 * 工作流可视化画布组件
 * 将数据库中的 workflow nodes/edges 转换为 React Flow 格式并渲染
 */
export function WorkflowCanvas({ nodes: dbNodes, edges: dbEdges, className }: WorkflowCanvasProps) {
  // 转换节点数据为 React Flow 格式
  const initialNodes = useMemo(() => {
    // 按执行顺序排序
    const sortedNodes = [...dbNodes].sort((a, b) => a.execution_order - b.execution_order)
    
    // 计算节点位置（简单的水平布局）
    const nodeSpacingX = 280
    const nodeSpacingY = 100
    const startX = 50
    const startY = 150
    
    // 添加 START 节点
    const flowNodes: Node[] = [
      {
        id: 'START',
        type: 'input',
        position: { x: startX, y: startY },
        data: { label: '🚀 START' },
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
    
    // 添加工作流节点
    sortedNodes.forEach((node, index) => {
      const category = node.category || 'general'
      const color = CATEGORY_COLORS[category] || CATEGORY_COLORS.general
      
      flowNodes.push({
        id: node.name,
        type: 'workflow',
        position: { 
          x: startX + (index + 1) * nodeSpacingX,
          y: startY - 30 + (index % 2) * 60, // 交替上下偏移
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
        },
        sourcePosition: Position.Right,
        targetPosition: Position.Left,
      })
    })
    
    // 添加 END 节点
    flowNodes.push({
      id: 'END',
      type: 'output',
      position: { 
        x: startX + (sortedNodes.length + 1) * nodeSpacingX,
        y: startY,
      },
      data: { label: '🏁 END' },
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
  }, [dbNodes])
  
  // 转换边数据为 React Flow 格式
  const initialEdges = useMemo(() => {
    const flowEdges: Edge[] = dbEdges.map((edge) => ({
      id: `e-${edge.from_node}-${edge.to_node}`,
      source: edge.from_node,
      target: edge.to_node,
      label: edge.condition || undefined,
      type: edge.condition ? 'smoothstep' : 'default',
      animated: !!edge.condition,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edge.condition ? '#f59e0b' : '#64748b',
      },
      style: {
        stroke: edge.condition ? '#f59e0b' : '#64748b',
        strokeWidth: 2,
      },
      labelStyle: {
        fill: '#f59e0b',
        fontWeight: 600,
        fontSize: 12,
      },
      labelBgStyle: {
        fill: '#fef3c7',
        fillOpacity: 0.9,
      },
    }))
    
    return flowEdges
  }, [dbEdges])
  
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  // 节点类型映射（useMemo 避免重复创建）
  const nodeTypes = useMemo(() => ({ workflow: WorkflowNode }), [])

  return (
    <div className={`h-[500px] border rounded-lg bg-slate-50 dark:bg-slate-900 ${className || ''}`}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-right"
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#94a3b8" gap={20} size={1} />
        <Controls className="bg-white dark:bg-slate-800" />
        <MiniMap 
          nodeStrokeWidth={3}
          className="bg-white dark:bg-slate-800"
        />
      </ReactFlow>
    </div>
  )
}

