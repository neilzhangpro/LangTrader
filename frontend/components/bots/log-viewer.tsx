'use client'

import { useQuery } from '@tanstack/react-query'
import { RefreshCw, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import * as botsApi from '@/lib/api/bots'

interface LogViewerProps {
  botId: number
  lines?: number
}

/**
 * 日志查看器组件
 */
export function LogViewer({ botId, lines = 100 }: LogViewerProps) {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['bot-logs', botId, lines],
    queryFn: () => botsApi.getBotLogs(botId, lines),
    refetchInterval: 10000, // 每 10 秒自动刷新
  })

  const handleDownload = () => {
    if (!data?.logs) return
    
    const blob = new Blob([data.logs], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `bot-${botId}-logs.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      {/* 工具栏 */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Showing last {lines} lines
        </p>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={`h-4 w-4 mr-1 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button 
            variant="outline" 
            size="sm"
            onClick={handleDownload}
            disabled={!data?.logs}
          >
            <Download className="h-4 w-4 mr-1" />
            Download
          </Button>
        </div>
      </div>

      {/* 日志内容 */}
      <div className="bg-background border rounded-lg p-4 h-[500px] overflow-auto">
        {isLoading ? (
          <div className="text-muted-foreground animate-pulse">
            Loading logs...
          </div>
        ) : data?.logs ? (
          <pre className="text-xs font-mono whitespace-pre-wrap text-muted-foreground">
            {data.logs}
          </pre>
        ) : (
          <div className="text-muted-foreground text-center py-8">
            No logs available
          </div>
        )}
      </div>
    </div>
  )
}

