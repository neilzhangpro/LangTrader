'use client'

import { memo } from 'react'
import { Handle, Position } from '@xyflow/react'
import { 
  Database, 
  Brain, 
  LineChart, 
  Zap, 
  Activity,
  Plug,
  Bot,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

// 类别图标映射
const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  data_source: <Database className="h-4 w-4" />,
  analysis: <LineChart className="h-4 w-4" />,
  decision: <Brain className="h-4 w-4" />,
  execution: <Zap className="h-4 w-4" />,
  monitoring: <Activity className="h-4 w-4" />,
  general: <Plug className="h-4 w-4" />,
}

interface WorkflowNodeData {
  label: string
  name: string
  pluginName: string
  enabled: boolean
  category: string
  color: string
  description?: string
  requiresLlm?: boolean
  requiresTrader?: boolean
  executionOrder: number
}

interface WorkflowNodeProps {
  data: WorkflowNodeData
  selected?: boolean
}

/**
 * 自定义工作流节点组件
 * 显示节点名称、类别图标、状态徽章等信息
 */
function WorkflowNodeComponent({ data, selected }: WorkflowNodeProps) {
  const icon = CATEGORY_ICONS[data.category] || CATEGORY_ICONS.general
  
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={`
              relative px-4 py-3 rounded-lg shadow-md border-2 min-w-[160px]
              transition-all duration-200
              ${data.enabled 
                ? 'bg-white dark:bg-slate-800' 
                : 'bg-slate-100 dark:bg-slate-900 opacity-60'
              }
              ${selected 
                ? 'ring-2 ring-offset-2 ring-blue-500' 
                : ''
              }
            `}
            style={{ 
              borderColor: data.enabled ? data.color : '#94a3b8',
            }}
          >
            {/* 左侧连接点 */}
            <Handle
              type="target"
              position={Position.Left}
              className="!w-3 !h-3 !border-2 !border-white"
              style={{ background: data.color }}
            />
            
            {/* 节点内容 */}
            <div className="flex items-center gap-2">
              {/* 图标 */}
              <div 
                className="p-2 rounded-md"
                style={{ background: `${data.color}20`, color: data.color }}
              >
                {icon}
              </div>
              
              {/* 标题和信息 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="font-medium text-sm truncate">
                    {data.label}
                  </span>
                  {!data.enabled && (
                    <Badge variant="secondary" className="text-[10px] px-1 py-0">
                      Disabled
                    </Badge>
                  )}
                </div>
                <div className="text-xs text-muted-foreground truncate">
                  {data.pluginName}
                </div>
              </div>
            </div>
            
            {/* 需求标识 */}
            <div className="absolute -top-2 -right-2 flex gap-1">
              {data.requiresLlm && (
                <div 
                  className="w-5 h-5 rounded-full bg-purple-500 flex items-center justify-center"
                  title="Requires LLM"
                >
                  <Brain className="h-3 w-3 text-white" />
                </div>
              )}
              {data.requiresTrader && (
                <div 
                  className="w-5 h-5 rounded-full bg-green-500 flex items-center justify-center"
                  title="Requires Trader"
                >
                  <Bot className="h-3 w-3 text-white" />
                </div>
              )}
            </div>
            
            {/* 执行顺序 */}
            <div 
              className="absolute -bottom-2 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-full text-[10px] font-medium text-white"
              style={{ background: data.color }}
            >
              #{data.executionOrder}
            </div>
            
            {/* 右侧连接点 */}
            <Handle
              type="source"
              position={Position.Right}
              className="!w-3 !h-3 !border-2 !border-white"
              style={{ background: data.color }}
            />
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-[300px]">
          <div className="space-y-1">
            <div className="font-medium">{data.label}</div>
            <div className="text-xs text-muted-foreground">
              Plugin: {data.pluginName}
            </div>
            {data.description && (
              <div className="text-xs">{data.description}</div>
            )}
            <div className="flex gap-2 pt-1">
              <Badge variant="outline" className="text-[10px]">
                {data.category}
              </Badge>
              {data.requiresLlm && (
                <Badge variant="secondary" className="text-[10px]">
                  LLM
                </Badge>
              )}
              {data.requiresTrader && (
                <Badge variant="secondary" className="text-[10px]">
                  Trader
                </Badge>
              )}
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export const WorkflowNode = memo(WorkflowNodeComponent)

