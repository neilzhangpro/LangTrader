'use client'

import { useQuery } from '@tanstack/react-query'
import { Activity, Filter, Calendar } from 'lucide-react'
import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { TradesTable } from '@/components/trades/trades-table'
import { formatCurrency } from '@/lib/utils'
import * as tradesApi from '@/lib/api/trades'
import * as botsApi from '@/lib/api/bots'

/**
 * 交易历史页面
 */
export default function TradesPage() {
  const [selectedBotId, setSelectedBotId] = useState<number | undefined>(undefined)
  const [page, setPage] = useState(1)

  // 获取 Bot 列表（用于筛选）
  const { data: botsData } = useQuery({
    queryKey: ['bots'],
    queryFn: () => botsApi.listBots({ page: 1, page_size: 100 }),
  })

  // 获取交易列表
  const { data: tradesData, isLoading } = useQuery({
    queryKey: ['trades', selectedBotId, page],
    queryFn: () => tradesApi.listTrades({ 
      bot_id: selectedBotId, 
      page, 
      page_size: 50 
    }),
  })

  // 获取交易摘要
  const { data: summary } = useQuery({
    queryKey: ['trade-summary', selectedBotId],
    queryFn: () => selectedBotId 
      ? tradesApi.getTradeSummary(selectedBotId, 'all')
      : Promise.resolve(null),
    enabled: !!selectedBotId,
  })

  const bots = botsData?.items || []
  const trades = tradesData?.items || []

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面标题 */}
      <div>
        <h1 className="text-3xl font-bold">Trade History</h1>
        <p className="text-muted-foreground">
          View all trades across your bots
        </p>
      </div>

      {/* 筛选器 */}
      <div className="flex gap-4">
        <Button
          variant={!selectedBotId ? 'default' : 'outline'}
          onClick={() => setSelectedBotId(undefined)}
        >
          All Bots
        </Button>
        {bots.map((bot) => (
          <Button
            key={bot.id}
            variant={selectedBotId === bot.id ? 'default' : 'outline'}
            onClick={() => setSelectedBotId(bot.id)}
          >
            {bot.name}
          </Button>
        ))}
      </div>

      {/* 摘要统计（选择特定 Bot 时显示） */}
      {summary && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Total Trades</p>
            <p className="text-2xl font-bold">{summary.total_trades}</p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Win / Loss</p>
            <p className="text-2xl font-bold">
              <span className="text-profit">{summary.winning_trades}</span>
              {' / '}
              <span className="text-loss">{summary.losing_trades}</span>
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Net PnL</p>
            <p className={`text-2xl font-bold ${summary.net_pnl_usd >= 0 ? 'text-profit' : 'text-loss'}`}>
              {formatCurrency(summary.net_pnl_usd)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">Avg Trade PnL</p>
            <p className={`text-2xl font-bold ${summary.avg_trade_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
              {formatCurrency(summary.avg_trade_pnl)}
            </p>
          </Card>
        </div>
      )}

      {/* 交易表格 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Trades
            {tradesData && (
              <span className="text-sm font-normal text-muted-foreground">
                ({tradesData.total} total)
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <TradesTable trades={trades} isLoading={isLoading} />
          
          {/* 分页 */}
          {tradesData && tradesData.total_pages > 1 && (
            <div className="flex justify-center gap-2 mt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="flex items-center px-4 text-sm text-muted-foreground">
                Page {page} of {tradesData.total_pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(tradesData.total_pages, p + 1))}
                disabled={page === tradesData.total_pages}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

