'use client'

import Link from 'next/link'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Play, Square, RefreshCw, MoreVertical, ExternalLink } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { StatusBadge } from './status-badge'
import { formatCurrency, formatUptime } from '@/lib/utils'
import * as botsApi from '@/lib/api/bots'
import type { BotSummary } from '@/types/api'

interface BotCardProps {
  bot: BotSummary
}

/**
 * Bot 卡片组件
 * 显示 Bot 概览信息和控制按钮
 */
export function BotCard({ bot }: BotCardProps) {
  const queryClient = useQueryClient()

  // 获取 Bot 状态
  const { data: status } = useQuery({
    queryKey: ['bot-status', bot.id],
    queryFn: () => botsApi.getBotStatus(bot.id),
    refetchInterval: 5000, // 每 5 秒刷新
  })

  // 启动 Bot
  const startMutation = useMutation({
    mutationFn: () => botsApi.startBot(bot.id),
    onSuccess: () => {
      // 立即刷新状态，而不是只标记缓存过期
      queryClient.refetchQueries({ queryKey: ['bot-status', bot.id] })
    },
  })

  // 停止 Bot
  const stopMutation = useMutation({
    mutationFn: () => botsApi.stopBot(bot.id),
    onSuccess: () => {
      // 立即刷新状态，确保 UI 同步更新
      queryClient.refetchQueries({ queryKey: ['bot-status', bot.id] })
    },
  })

  const isLoading = startMutation.isPending || stopMutation.isPending

  return (
    <Card className="hover:border-primary/50 transition-colors">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-lg font-medium">
          <Link 
            href={`/bots/${bot.id}`}
            className="hover:text-primary transition-colors flex items-center gap-2"
          >
            {bot.display_name || bot.name}
            <ExternalLink className="h-4 w-4 opacity-50" />
          </Link>
        </CardTitle>
        <StatusBadge 
          status={status?.state || 'unknown'} 
          isRunning={status?.is_running}
        />
      </CardHeader>
      <CardContent>
        {/* 统计信息 */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <p className="text-xs text-muted-foreground">Balance</p>
            <p className="text-lg font-mono font-semibold">
              {status?.balance != null 
                ? formatCurrency(status.balance)
                : '-'
              }
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Positions</p>
            <p className="text-lg font-mono font-semibold">
              {status?.open_positions ?? 0}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Cycle</p>
            <p className="text-sm font-mono">
              #{status?.current_cycle ?? 0}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Uptime</p>
            <p className="text-sm font-mono">
              {status?.uptime_seconds != null 
                ? formatUptime(status.uptime_seconds)
                : '-'
              }
            </p>
          </div>
        </div>

        {/* 交易模式标签 */}
        <div className="flex items-center gap-2 mb-4">
          <span className={`text-xs px-2 py-0.5 rounded ${
            bot.trading_mode === 'live' 
              ? 'bg-green-500/20 text-green-500' 
              : bot.trading_mode === 'paper'
                ? 'bg-yellow-500/20 text-yellow-500'
                : 'bg-blue-500/20 text-blue-500'
          }`}>
            {bot.trading_mode.toUpperCase()}
          </span>
        </div>

        {/* 控制按钮 */}
        <div className="flex gap-2">
          {status?.is_running ? (
            <Button 
              variant="destructive" 
              size="sm" 
              className="flex-1"
              onClick={() => stopMutation.mutate()}
              disabled={isLoading}
            >
              <Square className="h-4 w-4 mr-1" />
              Stop
            </Button>
          ) : (
            <Button 
              variant="success" 
              size="sm" 
              className="flex-1"
              onClick={() => startMutation.mutate()}
              disabled={isLoading || !bot.is_active}
            >
              <Play className="h-4 w-4 mr-1" />
              Start
            </Button>
          )}
          <Button 
            variant="outline" 
            size="sm"
            asChild
          >
            <Link href={`/bots/${bot.id}`}>
              <MoreVertical className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

