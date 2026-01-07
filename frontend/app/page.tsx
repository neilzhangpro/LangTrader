'use client'

import { useQuery } from '@tanstack/react-query'
import { 
  Bot, 
  DollarSign, 
  TrendingUp, 
  Activity,
  BarChart3,
  Percent
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { BotCard } from '@/components/bots/bot-card'
import { MetricsCard } from '@/components/dashboard/metrics-card'
import { PnLChart } from '@/components/charts/pnl-chart'
import { formatCurrency, formatPercent } from '@/lib/utils'
import * as botsApi from '@/lib/api/bots'
import * as performanceApi from '@/lib/api/performance'
import * as tradesApi from '@/lib/api/trades'

/**
 * Dashboard 首页
 * 展示系统概览：Bot 状态、总余额、绩效指标、PnL 图表
 */
export default function DashboardPage() {
  // 获取 Bot 列表
  const { data: botsData, isLoading: isLoadingBots } = useQuery({
    queryKey: ['bots'],
    queryFn: () => botsApi.listBots({ page: 1, page_size: 100 }),
  })

  // 获取第一个 Bot 的绩效数据（用于演示）
  const firstBotId = botsData?.items?.[0]?.id
  
  const { data: performance } = useQuery({
    queryKey: ['performance', firstBotId],
    queryFn: () => performanceApi.getBotPerformance(firstBotId!),
    enabled: !!firstBotId,
  })

  const { data: dailyPerformance } = useQuery({
    queryKey: ['daily-performance', firstBotId],
    queryFn: () => tradesApi.getDailyPerformance(firstBotId!, 30),
    enabled: !!firstBotId,
  })

  const { data: tradeSummary } = useQuery({
    queryKey: ['trade-summary', firstBotId],
    queryFn: () => tradesApi.getTradeSummary(firstBotId!, 'all'),
    enabled: !!firstBotId,
  })

  const bots = botsData?.items || []
  const runningBots = bots.filter(b => b.is_active).length

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面标题 */}
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your trading bots and performance
        </p>
      </div>

      {/* 关键指标卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricsCard
          title="Active Bots"
          value={`${runningBots} / ${bots.length}`}
          subtitle="running bots"
          icon={Bot}
        />
        <MetricsCard
          title="Total PnL"
          value={formatCurrency(tradeSummary?.net_pnl_usd ?? 0)}
          subtitle="all time"
          icon={DollarSign}
          isPnL
          trend={tradeSummary?.net_pnl_usd && tradeSummary.net_pnl_usd > 0 ? 'up' : 'down'}
        />
        <MetricsCard
          title="Win Rate"
          value={formatPercent((performance?.win_rate ?? 0) * 100, 1)}
          subtitle={`${performance?.total_trades ?? 0} trades`}
          icon={Percent}
          trend={(performance?.win_rate ?? 0) > 0.5 ? 'up' : 'down'}
        />
        <MetricsCard
          title="Sharpe Ratio"
          value={(performance?.sharpe_ratio ?? 0).toFixed(2)}
          subtitle="risk-adjusted"
          icon={BarChart3}
          trend={(performance?.sharpe_ratio ?? 0) > 1 ? 'up' : 'neutral'}
        />
      </div>

      {/* PnL 图表 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Performance (Last 30 Days)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {dailyPerformance && dailyPerformance.length > 0 ? (
            <PnLChart data={dailyPerformance} height={300} />
          ) : (
            <div className="h-[300px] flex items-center justify-center text-muted-foreground">
              No performance data available
            </div>
          )}
        </CardContent>
      </Card>

      {/* Bot 卡片网格 */}
      <div>
        <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Trading Bots
        </h2>
        {isLoadingBots ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <Card key={i} className="h-64 animate-pulse bg-muted" />
            ))}
          </div>
        ) : bots.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {bots.map((bot) => (
              <BotCard key={bot.id} bot={bot} />
            ))}
          </div>
        ) : (
          <Card className="p-8 text-center">
            <Bot className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
            <h3 className="text-lg font-medium mb-2">No Bots Yet</h3>
            <p className="text-muted-foreground">
              Create your first trading bot to get started
            </p>
          </Card>
        )}
      </div>
    </div>
  )
}

