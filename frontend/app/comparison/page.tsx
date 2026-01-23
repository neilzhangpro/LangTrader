'use client'

import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  BarChart3, 
  RefreshCw, 
  TrendingUp, 
  TrendingDown,
  Trophy,
  X
} from 'lucide-react'
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Legend 
} from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatCurrency, formatPercent } from '@/lib/utils'
import * as botsApi from '@/lib/api/bots'
import * as performanceApi from '@/lib/api/performance'
import * as tradesApi from '@/lib/api/trades'

// 预定义的线条颜色
const LINE_COLORS = [
  'hsl(var(--primary))',
  'hsl(142, 76%, 36%)',  // green
  'hsl(38, 92%, 50%)',   // orange
  'hsl(280, 87%, 65%)',  // purple
  'hsl(199, 89%, 48%)',  // cyan
]

/**
 * 策略对比页面
 * 用于对比多个 Bot 的交易性能
 */
export default function ComparisonPage() {
  // 选中的 Bot IDs
  const [selectedBotIds, setSelectedBotIds] = useState<number[]>([])
  // 时间窗口（天数）
  const [timeWindow, setTimeWindow] = useState<number>(30)

  // 获取 Bot 列表（只显示 paper/live 模式）
  const { data: botsData, isLoading: isLoadingBots } = useQuery({
    queryKey: ['bots'],
    queryFn: () => botsApi.listBots({ page: 1, page_size: 100 }),
  })

  // 筛选 paper/live 模式的 Bot
  const availableBots = useMemo(() => {
    if (!botsData?.items) return []
    return botsData.items.filter(
      bot => bot.trading_mode === 'paper' || bot.trading_mode === 'live'
    )
  }, [botsData])

  // 获取性能对比数据
  const { data: comparisonData, isLoading: isLoadingComparison, refetch } = useQuery({
    queryKey: ['performance-compare', selectedBotIds, timeWindow],
    queryFn: () => performanceApi.compareBotsPerformance(selectedBotIds, timeWindow),
    enabled: selectedBotIds.length > 0,
  })

  // 获取每个选中 Bot 的每日绩效（用于图表）
  const { data: dailyPerformanceData } = useQuery({
    queryKey: ['daily-performance-multi', selectedBotIds, timeWindow],
    queryFn: async () => {
      const results = await Promise.all(
        selectedBotIds.map(async (botId) => {
          try {
            const data = await tradesApi.getDailyPerformance(botId, timeWindow)
            return { botId, data }
          } catch {
            return { botId, data: [] }
          }
        })
      )
      return results
    },
    enabled: selectedBotIds.length > 0,
  })

  // 处理 Bot 选择
  const handleBotSelect = (botIdStr: string) => {
    const botId = parseInt(botIdStr)
    if (!selectedBotIds.includes(botId)) {
      setSelectedBotIds([...selectedBotIds, botId])
    }
  }

  // 移除选中的 Bot
  const handleRemoveBot = (botId: number) => {
    setSelectedBotIds(selectedBotIds.filter(id => id !== botId))
  }

  // 准备图表数据（合并多个 Bot 的每日数据）
  const chartData = useMemo(() => {
    if (!dailyPerformanceData || dailyPerformanceData.length === 0) return []

    // 收集所有日期
    const dateMap = new Map<string, { date: string; [key: string]: string | number }>()
    
    dailyPerformanceData.forEach(({ botId, data }) => {
      let cumulative = 0
      data.forEach(item => {
        cumulative += item.pnl_usd
        const dateStr = new Date(item.date).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric'
        })
        
        if (!dateMap.has(dateStr)) {
          dateMap.set(dateStr, { date: dateStr })
        }
        dateMap.get(dateStr)![`bot_${botId}`] = cumulative
      })
    })

    return Array.from(dateMap.values())
  }, [dailyPerformanceData])

  // 获取 Bot 名称映射
  const botNameMap = useMemo(() => {
    const map: Record<number, string> = {}
    availableBots.forEach(bot => {
      map[bot.id] = bot.display_name || bot.name
    })
    return map
  }, [availableBots])

  // 找出最佳指标
  const getBestValue = (metric: string, higher: boolean = true) => {
    if (!comparisonData?.bots) return null
    let bestId: number | null = null
    let bestValue: number | null = null
    
    Object.entries(comparisonData.bots).forEach(([idStr, data]) => {
      const value = (data as Record<string, number | undefined>)[metric]
      if (value !== undefined && !isNaN(value)) {
        if (bestValue === null || (higher ? value > bestValue : value < bestValue)) {
          bestValue = value
          bestId = parseInt(idStr)
        }
      }
    })
    return bestId
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <BarChart3 className="h-8 w-8" />
            Strategy Comparison
          </h1>
          <p className="text-muted-foreground">
            Compare performance across multiple trading bots
          </p>
        </div>
        <Button 
          variant="outline" 
          onClick={() => refetch()}
          disabled={selectedBotIds.length === 0}
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* 选择器区域 */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center gap-4">
            {/* Bot 选择器 */}
            <div className="flex-1 min-w-[200px]">
              <Select onValueChange={handleBotSelect}>
                <SelectTrigger>
                  <SelectValue placeholder="Add bot to compare..." />
                </SelectTrigger>
                <SelectContent>
                  {isLoadingBots ? (
                    <SelectItem value="loading" disabled>Loading...</SelectItem>
                  ) : availableBots.length === 0 ? (
                    <SelectItem value="empty" disabled>No bots available</SelectItem>
                  ) : (
                    availableBots
                      .filter(bot => !selectedBotIds.includes(bot.id))
                      .map(bot => (
                        <SelectItem key={bot.id} value={bot.id.toString()}>
                          <div className="flex items-center gap-2">
                            <span>{bot.display_name || bot.name}</span>
                            <Badge variant="outline" className="text-xs">
                              {bot.trading_mode}
                            </Badge>
                          </div>
                        </SelectItem>
                      ))
                  )}
                </SelectContent>
              </Select>
            </div>

            {/* 时间范围选择器 */}
            <Select value={timeWindow.toString()} onValueChange={(v) => setTimeWindow(parseInt(v))}>
              <SelectTrigger className="w-[140px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="7">Last 7 days</SelectItem>
                <SelectItem value="30">Last 30 days</SelectItem>
                <SelectItem value="90">Last 90 days</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* 已选中的 Bot 标签 */}
          {selectedBotIds.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-4">
              {selectedBotIds.map((botId, index) => (
                <Badge 
                  key={botId} 
                  variant="secondary"
                  className="pl-3 pr-1 py-1 flex items-center gap-2"
                  style={{ borderLeftColor: LINE_COLORS[index % LINE_COLORS.length], borderLeftWidth: 3 }}
                >
                  {botNameMap[botId] || `Bot ${botId}`}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-5 w-5 p-0 hover:bg-destructive hover:text-destructive-foreground rounded-full"
                    onClick={() => handleRemoveBot(botId)}
                  >
                    <X className="h-3 w-3" />
                  </Button>
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 无选择提示 */}
      {selectedBotIds.length === 0 && (
        <Card className="p-12 text-center">
          <BarChart3 className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium mb-2">Select Bots to Compare</h3>
          <p className="text-muted-foreground max-w-md mx-auto">
            Choose two or more Paper Trading or Live bots from the dropdown above 
            to compare their performance side by side.
          </p>
        </Card>
      )}

      {/* 图表和表格 */}
      {selectedBotIds.length > 0 && (
        <>
          {/* 累计收益曲线图 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                Cumulative PnL Comparison
              </CardTitle>
            </CardHeader>
            <CardContent>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                    <XAxis 
                      dataKey="date" 
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                    />
                    <YAxis 
                      stroke="hsl(var(--muted-foreground))"
                      fontSize={12}
                      tickFormatter={(value) => `$${value.toFixed(0)}`}
                    />
                    <Tooltip 
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                      }}
                      labelStyle={{ color: 'hsl(var(--foreground))' }}
                      formatter={(value: number, name: string) => {
                        const botId = parseInt(name.replace('bot_', ''))
                        return [`$${value.toFixed(2)}`, botNameMap[botId] || name]
                      }}
                    />
                    <Legend 
                      formatter={(value: string) => {
                        const botId = parseInt(value.replace('bot_', ''))
                        return botNameMap[botId] || value
                      }}
                    />
                    {selectedBotIds.map((botId, index) => (
                      <Line 
                        key={botId}
                        type="monotone" 
                        dataKey={`bot_${botId}`}
                        stroke={LINE_COLORS[index % LINE_COLORS.length]}
                        strokeWidth={2}
                        dot={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[400px] flex items-center justify-center text-muted-foreground">
                  {isLoadingComparison ? (
                    <RefreshCw className="h-8 w-8 animate-spin" />
                  ) : (
                    'No performance data available'
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* 性能对比表格 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="h-5 w-5" />
                Performance Metrics
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoadingComparison ? (
                <div className="flex items-center justify-center py-12">
                  <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                </div>
              ) : comparisonData?.bots ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[180px]">Metric</TableHead>
                      {selectedBotIds.map((botId, index) => (
                        <TableHead key={botId}>
                          <div className="flex items-center gap-2">
                            <div 
                              className="w-3 h-3 rounded-full" 
                              style={{ backgroundColor: LINE_COLORS[index % LINE_COLORS.length] }}
                            />
                            {botNameMap[botId] || `Bot ${botId}`}
                          </div>
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {/* 总收益 */}
                    <TableRow>
                      <TableCell className="font-medium">Total Return</TableCell>
                      {selectedBotIds.map(botId => {
                        const data = comparisonData.bots[botId]
                        const isBest = getBestValue('total_return_usd', true) === botId
                        const value = data?.total_return_usd
                        return (
                          <TableCell key={botId}>
                            <div className="flex items-center gap-2">
                              <span className={value && value > 0 ? 'text-green-500' : value && value < 0 ? 'text-red-500' : ''}>
                                {value !== undefined ? formatCurrency(value) : '-'}
                              </span>
                              {isBest && <Trophy className="h-4 w-4 text-yellow-500" />}
                            </div>
                          </TableCell>
                        )
                      })}
                    </TableRow>
                    {/* 胜率 */}
                    <TableRow>
                      <TableCell className="font-medium">Win Rate</TableCell>
                      {selectedBotIds.map(botId => {
                        const data = comparisonData.bots[botId]
                        const isBest = getBestValue('win_rate', true) === botId
                        return (
                          <TableCell key={botId}>
                            <div className="flex items-center gap-2">
                              {data?.win_rate !== undefined ? formatPercent(data.win_rate, 1) : '-'}
                              {isBest && <Trophy className="h-4 w-4 text-yellow-500" />}
                            </div>
                          </TableCell>
                        )
                      })}
                    </TableRow>
                    {/* Sharpe Ratio */}
                    <TableRow>
                      <TableCell className="font-medium">Sharpe Ratio</TableCell>
                      {selectedBotIds.map(botId => {
                        const data = comparisonData.bots[botId]
                        const isBest = getBestValue('sharpe_ratio', true) === botId
                        return (
                          <TableCell key={botId}>
                            <div className="flex items-center gap-2">
                              {data?.sharpe_ratio !== undefined ? data.sharpe_ratio.toFixed(2) : '-'}
                              {isBest && <Trophy className="h-4 w-4 text-yellow-500" />}
                            </div>
                          </TableCell>
                        )
                      })}
                    </TableRow>
                    {/* 最大回撤 */}
                    <TableRow>
                      <TableCell className="font-medium">Max Drawdown</TableCell>
                      {selectedBotIds.map(botId => {
                        const data = comparisonData.bots[botId]
                        const isBest = getBestValue('max_drawdown', false) === botId
                        return (
                          <TableCell key={botId}>
                            <div className="flex items-center gap-2">
                              <span className="text-red-500">
                                {data?.max_drawdown !== undefined ? formatPercent(data.max_drawdown * 100, 2) : '-'}
                              </span>
                              {isBest && <Trophy className="h-4 w-4 text-yellow-500" />}
                            </div>
                          </TableCell>
                        )
                      })}
                    </TableRow>
                    {/* 交易次数 */}
                    <TableRow>
                      <TableCell className="font-medium">Total Trades</TableCell>
                      {selectedBotIds.map(botId => {
                        const data = comparisonData.bots[botId]
                        return (
                          <TableCell key={botId}>
                            {data?.total_trades ?? '-'}
                          </TableCell>
                        )
                      })}
                    </TableRow>
                  </TableBody>
                </Table>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  No comparison data available
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

