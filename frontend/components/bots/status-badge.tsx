'use client'

import { Badge } from '@/components/ui/badge'
import type { BotStatus } from '@/types/api'

interface StatusBadgeProps {
  status: BotStatus['state']
  isRunning?: boolean
}

/**
 * Bot 状态徽章组件
 */
export function StatusBadge({ status, isRunning }: StatusBadgeProps) {
  // 根据状态确定样式
  const getVariant = () => {
    if (isRunning || status === 'running') return 'success'
    if (status === 'error') return 'error'
    if (status === 'idle') return 'warning'
    return 'secondary'
  }

  const getLabel = () => {
    if (isRunning || status === 'running') return 'Running'
    if (status === 'error') return 'Error'
    if (status === 'idle') return 'Idle'
    if (status === 'stopped') return 'Stopped'
    return 'Unknown'
  }

  return (
    <Badge variant={getVariant()} className="gap-1.5">
      <span className={`h-2 w-2 rounded-full ${
        isRunning || status === 'running' 
          ? 'bg-green-500 animate-pulse' 
          : status === 'error' 
            ? 'bg-red-500' 
            : 'bg-gray-500'
      }`} />
      {getLabel()}
    </Badge>
  )
}

