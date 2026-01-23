'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { 
  ArrowLeft, 
  Play, 
  Square, 
  RefreshCw,
  BarChart3,
  Activity,
  FileText,
  Settings,
  Wallet,
  TrendingUp,
  Percent,
  DollarSign,
  MessageSquare,
  Trash2,
  Edit
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { StatusBadge } from '@/components/bots/status-badge'
import { PositionsTable } from '@/components/bots/positions-table'
import { TradesTable } from '@/components/trades/trades-table'
import { LogViewer } from '@/components/bots/log-viewer'
import { DebateViewer } from '@/components/bots/debate-viewer'
import { EditBotDialog } from '@/components/bots/edit-bot-dialog'
import { PnLChart } from '@/components/charts/pnl-chart'
import { MetricsCard } from '@/components/dashboard/metrics-card'
import { toast } from '@/components/ui/use-toast'
import { formatCurrency, formatPercent, formatUptime } from '@/lib/utils'
import * as botsApi from '@/lib/api/bots'
import * as performanceApi from '@/lib/api/performance'
import * as tradesApi from '@/lib/api/trades'
import * as workflowsApi from '@/lib/api/workflows'
import * as llmConfigsApi from '@/lib/api/llm-configs'

/**
 * Bot 详情页面
 * 展示完整的 Bot 信息，包括状态、持仓、交易历史、日志和设置
 */
export default function BotDetailPage() {
  const params = useParams()
  const router = useRouter()
  const botId = Number(params.id)
  const queryClient = useQueryClient()

  // 获取 Bot 详情
  const { data: bot, isLoading: isLoadingBot } = useQuery({
    queryKey: ['bot', botId],
    queryFn: () => botsApi.getBot(botId),
  })

  // 获取 Bot 状态
  const { data: status } = useQuery({
    queryKey: ['bot-status', botId],
    queryFn: () => botsApi.getBotStatus(botId),
    refetchInterval: 5000,
  })

  // 获取持仓
  const { data: positions, isLoading: isLoadingPositions } = useQuery({
    queryKey: ['bot-positions', botId],
    queryFn: () => botsApi.getBotPositions(botId),
    refetchInterval: 10000,
  })

  // 获取余额
  const { data: balance } = useQuery({
    queryKey: ['bot-balance', botId],
    queryFn: () => botsApi.getBotBalance(botId),
    refetchInterval: 30000,
  })

  // 获取绩效
  const { data: performance } = useQuery({
    queryKey: ['performance', botId],
    queryFn: () => performanceApi.getBotPerformance(botId),
  })

  // 获取每日绩效（用于图表）
  const { data: dailyPerformance } = useQuery({
    queryKey: ['daily-performance', botId],
    queryFn: () => tradesApi.getDailyPerformance(botId, 30),
  })

  // 获取交易历史
  const { data: tradesData, isLoading: isLoadingTrades } = useQuery({
    queryKey: ['trades', botId],
    queryFn: () => tradesApi.listTrades({ bot_id: botId, page: 1, page_size: 50 }),
  })

  // 获取 AI 辩论结果
  const { data: debate, isLoading: isLoadingDebate } = useQuery({
    queryKey: ['bot-debate', botId],
    queryFn: () => botsApi.getBotDebate(botId),
    refetchInterval: 15000, // 每15秒刷新一次
  })

  // 获取 Workflow 详情（用于读取debate_decision节点配置）
  const { data: workflow } = useQuery({
    queryKey: ['workflow', bot?.workflow_id],
    queryFn: () => workflowsApi.getWorkflow(bot!.workflow_id),
    enabled: !!bot?.workflow_id, // 只有当bot存在且有workflow_id时才查询
  })

  // 获取 LLM 配置列表（用于建立ID到模型名的映射）
  const { data: llmConfigs } = useQuery({
    queryKey: ['llm-configs'],
    queryFn: () => llmConfigsApi.listLLMConfigs(),
  })

  // 计算角色LLM信息映射（从workflow配置中读取debate_decision节点的role_llm_ids）
  const roleLlmInfo = useMemo(() => {
    if (!workflow?.nodes || !llmConfigs) {
      return {}
    }

    // 找到debate_decision节点
    const debateNode = workflow.nodes.find(node => node.plugin_name === 'debate_decision')
    if (!debateNode || !debateNode.config) {
      return {}
    }

    const roleLlmIds = debateNode.config.role_llm_ids as Record<string, number> | undefined
    if (!roleLlmIds || typeof roleLlmIds !== 'object') {
      return {}
    }

    // 建立LLM ID到配置的映射
    const llmMap = new Map(llmConfigs.map(llm => [llm.id, llm]))

    // 生成角色到LLM信息的映射
    const result: Record<string, { id: number; model_name: string; display_name?: string }> = {}
    for (const [role, llmId] of Object.entries(roleLlmIds)) {
      const llm = llmMap.get(llmId)
      if (llm) {
        result[role] = {
          id: llm.id,
          model_name: llm.model_name,
          display_name: llm.display_name,
        }
      }
    }

    return result
  }, [workflow, llmConfigs])

  // 启动/停止操作 - 使用 refetchQueries 立即刷新状态
  const startMutation = useMutation({
    mutationFn: () => botsApi.startBot(botId),
    onSuccess: () => queryClient.refetchQueries({ queryKey: ['bot-status', botId] }),
  })

  const stopMutation = useMutation({
    mutationFn: () => botsApi.stopBot(botId),
    onSuccess: () => queryClient.refetchQueries({ queryKey: ['bot-status', botId] }),
  })

  const restartMutation = useMutation({
    mutationFn: () => botsApi.restartBot(botId),
    onSuccess: () => queryClient.refetchQueries({ queryKey: ['bot-status', botId] }),
  })

  // 删除 Bot
  const deleteMutation = useMutation({
    mutationFn: () => botsApi.deleteBot(botId),
    onSuccess: () => {
      toast({
        title: 'Bot Deleted',
        description: 'The bot has been deleted successfully.',
      })
      queryClient.invalidateQueries({ queryKey: ['bots'] })
      router.push('/bots')
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to delete bot',
        variant: 'destructive',
      })
    },
  })

  const isControlLoading = startMutation.isPending || stopMutation.isPending || restartMutation.isPending

  if (isLoadingBot) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (!bot) {
    return (
      <div className="text-center py-12">
        <h2 className="text-xl font-semibold mb-2">Bot Not Found</h2>
        <p className="text-muted-foreground mb-4">
          The requested bot could not be found.
        </p>
        <Button asChild>
          <Link href="/bots">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Bots
          </Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面头部 */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/bots">
              <ArrowLeft className="h-5 w-5" />
            </Link>
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-bold">
                {bot.display_name || bot.name}
              </h1>
              <StatusBadge 
                status={status?.state || 'unknown'} 
                isRunning={status?.is_running}
              />
            </div>
            <p className="text-muted-foreground">{bot.description || 'No description'}</p>
          </div>
        </div>
        
        {/* 控制按钮 */}
        <div className="flex gap-2">
          {status?.is_running ? (
            <>
              <Button 
                variant="outline"
                onClick={() => restartMutation.mutate()}
                disabled={isControlLoading}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${restartMutation.isPending ? 'animate-spin' : ''}`} />
                Restart
              </Button>
              <Button 
                variant="destructive"
                onClick={() => stopMutation.mutate()}
                disabled={isControlLoading}
              >
                <Square className="h-4 w-4 mr-2" />
                Stop
              </Button>
            </>
          ) : (
            <Button 
              variant="success"
              onClick={() => startMutation.mutate()}
              disabled={isControlLoading || !bot.is_active}
            >
              <Play className="h-4 w-4 mr-2" />
              Start
            </Button>
          )}
        </div>
      </div>

      {/* 关键指标 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <MetricsCard
          title="Balance"
          value={formatCurrency(balance?.total_usd ?? status?.balance ?? 0)}
          subtitle={`Initial: ${formatCurrency(balance?.initial_balance ?? status?.initial_balance ?? bot.initial_balance ?? 0)}`}
          icon={Wallet}
        />
        <MetricsCard
          title="Current Cycle"
          value={`#${status?.current_cycle ?? 0}`}
          subtitle={status?.uptime_seconds != null ? `Uptime: ${formatUptime(status.uptime_seconds)}` : 'Not running'}
          icon={Activity}
        />
        <MetricsCard
          title="Win Rate"
          value={formatPercent(performance?.win_rate ?? 0, 1)}
          subtitle={`${performance?.total_trades ?? 0} total trades`}
          icon={Percent}
          trend={(performance?.win_rate ?? 0) > 50 ? 'up' : 'down'}
        />
        <MetricsCard
          title="Total PnL"
          value={formatCurrency(performance?.total_return_usd ?? 0)}
          subtitle={`Sharpe: ${(performance?.sharpe_ratio ?? 0).toFixed(2)}`}
          icon={DollarSign}
          isPnL
          trend={(performance?.total_return_usd ?? 0) > 0 ? 'up' : 'down'}
        />
      </div>

      {/* 标签页 */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview" className="gap-2">
            <Activity className="h-4 w-4" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="debate" className="gap-2">
            <MessageSquare className="h-4 w-4" />
            AI Decision
          </TabsTrigger>
          <TabsTrigger value="performance" className="gap-2">
            <BarChart3 className="h-4 w-4" />
            Performance
          </TabsTrigger>
          <TabsTrigger value="trades" className="gap-2">
            <TrendingUp className="h-4 w-4" />
            Trades
          </TabsTrigger>
          <TabsTrigger value="logs" className="gap-2">
            <FileText className="h-4 w-4" />
            Logs
          </TabsTrigger>
          <TabsTrigger value="settings" className="gap-2">
            <Settings className="h-4 w-4" />
            Settings
          </TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {/* 当前持仓 */}
          <Card>
            <CardHeader>
              <CardTitle>Open Positions</CardTitle>
            </CardHeader>
            <CardContent>
              <PositionsTable 
                positions={positions || []} 
                isLoading={isLoadingPositions}
              />
            </CardContent>
          </Card>

          {/* 交易中的币种 */}
          {status?.symbols_trading && status.symbols_trading.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Trading Symbols</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {status.symbols_trading.map((symbol) => (
                    <span 
                      key={symbol}
                      className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm font-mono"
                    >
                      {symbol}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* AI Debate Tab */}
        <TabsContent value="debate" className="space-y-4">
          <DebateViewer 
            debate={debate ?? null} 
            isLoading={isLoadingDebate}
            roleLlmInfo={roleLlmInfo}
          />
        </TabsContent>

        {/* Performance Tab */}
        <TabsContent value="performance" className="space-y-4">
          {/* PnL 图表 */}
          <Card>
            <CardHeader>
              <CardTitle>PnL History (Last 30 Days)</CardTitle>
            </CardHeader>
            <CardContent>
              {dailyPerformance && dailyPerformance.length > 0 ? (
                <PnLChart data={dailyPerformance} height={400} />
              ) : (
                <div className="h-[400px] flex items-center justify-center text-muted-foreground">
                  No performance data available
                </div>
              )}
            </CardContent>
          </Card>

          {/* 详细指标 */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">Winning Trades</p>
              <p className="text-2xl font-bold text-profit">
                {performance?.winning_trades ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">
                Avg: {formatPercent(performance?.avg_win_pct ?? 0)}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">Losing Trades</p>
              <p className="text-2xl font-bold text-loss">
                {performance?.losing_trades ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">
                Avg: {formatPercent(performance?.avg_loss_pct ?? 0)}
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-sm text-muted-foreground">Max Drawdown</p>
              <p className="text-2xl font-bold text-loss">
                {formatPercent(performance?.max_drawdown ?? 0)}
              </p>
            </Card>
          </div>
        </TabsContent>

        {/* Trades Tab */}
        <TabsContent value="trades">
          <Card>
            <CardHeader>
              <CardTitle>Trade History</CardTitle>
            </CardHeader>
            <CardContent>
              <TradesTable 
                trades={tradesData?.items || []} 
                isLoading={isLoadingTrades}
              />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Logs Tab */}
        <TabsContent value="logs">
          <Card>
            <CardHeader>
              <CardTitle>Runtime Logs</CardTitle>
            </CardHeader>
            <CardContent>
              <LogViewer botId={botId} lines={200} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Bot Configuration</CardTitle>
              <div className="flex gap-2">
                <EditBotDialog bot={bot}>
                  <Button variant="outline" size="sm">
                    <Edit className="h-4 w-4 mr-2" />
                    Edit
                  </Button>
                </EditBotDialog>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <p className="text-sm text-muted-foreground">Name</p>
                  <p className="font-medium">{bot.name}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Trading Mode</p>
                  <p className="font-medium capitalize">{bot.trading_mode}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Max Leverage</p>
                  <p className="font-medium">{bot.max_leverage}x</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Cycle Interval</p>
                  <p className="font-medium">{bot.cycle_interval_seconds}s</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Max Concurrent Symbols</p>
                  <p className="font-medium">{bot.max_concurrent_symbols}</p>
                </div>
              </div>

              {bot.risk_limits && (
                <div className="mt-6">
                  <p className="text-sm text-muted-foreground mb-2">Risk Limits</p>
                  <pre className="bg-muted p-4 rounded-lg text-xs overflow-auto">
                    {JSON.stringify(bot.risk_limits, null, 2)}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 危险区域 */}
          <Card className="border-destructive/50">
            <CardHeader>
              <CardTitle className="text-destructive">Danger Zone</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Delete this bot</p>
                  <p className="text-sm text-muted-foreground">
                    Once deleted, this bot and all its data cannot be recovered.
                  </p>
                </div>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="destructive" disabled={status?.is_running}>
                      <Trash2 className="h-4 w-4 mr-2" />
                      Delete Bot
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete Bot</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to delete &quot;{bot.display_name || bot.name}&quot;?
                        This action cannot be undone. All trading history and configurations will be permanently removed.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        onClick={() => deleteMutation.mutate()}
                      >
                        {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
              {status?.is_running && (
                <p className="text-sm text-yellow-500 mt-2">
                  ⚠️ Stop the bot before deleting
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}

