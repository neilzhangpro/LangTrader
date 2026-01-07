'use client'

import { 
  Database, 
  Brain, 
  LineChart, 
  Zap, 
  Activity,
  Plug,
  GripVertical,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { ScrollArea } from '@/components/ui/scroll-area'

// 类别图标映射
const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  data_source: <Database className="h-4 w-4" />,
  analysis: <LineChart className="h-4 w-4" />,
  decision: <Brain className="h-4 w-4" />,
  execution: <Zap className="h-4 w-4" />,
  monitoring: <Activity className="h-4 w-4" />,
  Basic: <Plug className="h-4 w-4" />,
  general: <Plug className="h-4 w-4" />,
}

// 类别颜色
const CATEGORY_COLORS: Record<string, string> = {
  data_source: '#3b82f6',
  analysis: '#8b5cf6',
  decision: '#f59e0b',
  execution: '#10b981',
  monitoring: '#6366f1',
  Basic: '#64748b',
  general: '#64748b',
}

export interface PluginInfo {
  name: string
  display_name: string
  description?: string
  category: string
  version?: string
  author?: string
  requires_llm?: boolean
  requires_trader?: boolean
  suggested_order?: number
}

interface PluginLibraryProps {
  plugins: PluginInfo[]
  className?: string
}

/**
 * 插件库组件
 * 显示可拖拽的插件列表，按类别分组
 */
export function PluginLibrary({ plugins, className }: PluginLibraryProps) {
  // 按类别分组
  const groupedPlugins = plugins.reduce((acc, plugin) => {
    const category = plugin.category || 'general'
    if (!acc[category]) {
      acc[category] = []
    }
    acc[category].push(plugin)
    return acc
  }, {} as Record<string, PluginInfo[]>)

  return (
    <div className={`w-64 border-r bg-slate-50 dark:bg-slate-900 ${className || ''}`}>
      <div className="p-4 border-b">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <Plug className="h-4 w-4" />
          插件库
        </h3>
        <p className="text-xs text-muted-foreground mt-1">
          拖拽插件到画布添加节点
        </p>
      </div>
      
      <ScrollArea className="h-[calc(100%-80px)]">
        <div className="p-3 space-y-4">
          {Object.entries(groupedPlugins).map(([category, categoryPlugins]) => (
            <div key={category}>
              <h4 
                className="text-xs font-medium uppercase tracking-wider mb-2 px-2"
                style={{ color: CATEGORY_COLORS[category] || CATEGORY_COLORS.general }}
              >
                {category}
              </h4>
              <div className="space-y-1">
                {categoryPlugins.map((plugin) => (
                  <DraggablePlugin key={plugin.name} plugin={plugin} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}

interface DraggablePluginProps {
  plugin: PluginInfo
}

/**
 * 可拖拽的插件卡片
 */
function DraggablePlugin({ plugin }: DraggablePluginProps) {
  const category = plugin.category || 'general'
  const color = CATEGORY_COLORS[category] || CATEGORY_COLORS.general
  const icon = CATEGORY_ICONS[category] || CATEGORY_ICONS.general

  const handleDragStart = (e: React.DragEvent) => {
    // 设置拖拽数据
    e.dataTransfer.setData('application/reactflow', JSON.stringify(plugin))
    e.dataTransfer.effectAllowed = 'move'
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            draggable
            onDragStart={handleDragStart}
            className="
              flex items-center gap-2 p-2 rounded-md cursor-grab
              bg-white dark:bg-slate-800 border
              hover:shadow-md hover:border-blue-300 dark:hover:border-blue-600
              transition-all duration-200
              active:cursor-grabbing active:shadow-lg
            "
          >
            {/* 拖拽把手 */}
            <GripVertical className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            
            {/* 图标 */}
            <div 
              className="p-1.5 rounded"
              style={{ background: `${color}20`, color }}
            >
              {icon}
            </div>
            
            {/* 信息 */}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">
                {plugin.display_name}
              </div>
              <div className="flex items-center gap-1">
                {plugin.requires_llm && (
                  <Badge variant="secondary" className="text-[9px] px-1 py-0 h-4">
                    LLM
                  </Badge>
                )}
                {plugin.requires_trader && (
                  <Badge variant="secondary" className="text-[9px] px-1 py-0 h-4">
                    Trader
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </TooltipTrigger>
        <TooltipContent side="right" className="max-w-[250px]">
          <div className="space-y-1">
            <div className="font-medium">{plugin.display_name}</div>
            {plugin.description && (
              <div className="text-xs text-muted-foreground">
                {plugin.description}
              </div>
            )}
            <div className="text-xs">
              Plugin: <code className="bg-muted px-1 rounded">{plugin.name}</code>
            </div>
            {plugin.version && (
              <div className="text-xs text-muted-foreground">
                v{plugin.version} {plugin.author && `by ${plugin.author}`}
              </div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

