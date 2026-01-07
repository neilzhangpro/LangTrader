'use client'

import { Card, CardContent } from '@/components/ui/card'
import { cn, getPnLColorClass } from '@/lib/utils'
import { LucideIcon } from 'lucide-react'

interface MetricsCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: LucideIcon
  trend?: 'up' | 'down' | 'neutral'
  isPnL?: boolean
  className?: string
}

/**
 * 指标卡片组件
 * 用于展示单个关键指标
 */
export function MetricsCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  isPnL,
  className,
}: MetricsCardProps) {
  const numValue = typeof value === 'number' ? value : parseFloat(value)
  const valueColorClass = isPnL && !isNaN(numValue) ? getPnLColorClass(numValue) : ''

  return (
    <Card className={cn('animate-fade-in', className)}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className={cn(
              'text-2xl font-bold font-mono mt-1',
              valueColorClass
            )}>
              {value}
            </p>
            {subtitle && (
              <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>
            )}
          </div>
          {Icon && (
            <div className={cn(
              'h-10 w-10 rounded-lg flex items-center justify-center',
              trend === 'up' ? 'bg-profit/10 text-profit' :
              trend === 'down' ? 'bg-loss/10 text-loss' :
              'bg-primary/10 text-primary'
            )}>
              <Icon className="h-5 w-5" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

