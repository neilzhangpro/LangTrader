'use client'

/**
 * AI 决策查看器组件
 * 
 * 支持两种模式：
 * 1. 多角色辩论模式 (Debate) - 显示完整的辩论过程
 * 2. 批量决策模式 (Batch) - 仅显示最终决策
 */

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { 
  TrendingUp, 
  TrendingDown, 
  Minus, 
  User, 
  Shield,
  Clock,
  Target,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Zap
} from 'lucide-react'
import type { 
  DebateResult, 
  AnalystOutput, 
  TraderSuggestion,
  PortfolioDecision 
} from '@/lib/api/bots'

interface DebateViewerProps {
  debate: DebateResult | null
  isLoading?: boolean
  roleLlmInfo?: Record<string, { id: number; model_name: string; display_name?: string }>
}

/**
 * 判断是否为辩论模式
 * 如果有分析师输出或多空建议，则为辩论模式
 */
function isDebateMode(debate: DebateResult): boolean {
  return (
    (debate.analyst_outputs && debate.analyst_outputs.length > 0) ||
    (debate.bull_suggestions && debate.bull_suggestions.length > 0) ||
    (debate.bear_suggestions && debate.bear_suggestions.length > 0)
  )
}

/**
 * 趋势徽章组件
 */
function TrendBadge({ trend }: { trend: string }) {
  const variants: Record<string, { icon: typeof TrendingUp; color: string }> = {
    bullish: { icon: TrendingUp, color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
    bearish: { icon: TrendingDown, color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
    neutral: { icon: Minus, color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400' },
  }
  const v = variants[trend] || variants.neutral
  const Icon = v.icon
  return (
    <Badge variant="outline" className={v.color}>
      <Icon className="h-3 w-3 mr-1" />
      {trend}
    </Badge>
  )
}

/**
 * 操作徽章组件
 */
function ActionBadge({ action }: { action: string }) {
  const colors: Record<string, string> = {
    open_long: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    open_short: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    close_long: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    close_short: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    long: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    short: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    wait: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
  }
  return (
    <Badge variant="outline" className={colors[action] || colors.wait}>
      {action.replace('_', ' ')}
    </Badge>
  )
}

/**
 * 信心度指示器
 */
function ConfidenceIndicator({ confidence }: { confidence: number }) {
  const getColor = () => {
    if (confidence >= 70) return 'text-green-500'
    if (confidence >= 40) return 'text-yellow-500'
    return 'text-red-500'
  }
  
  return (
    <div className="flex items-center gap-1">
      <div className="w-16 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
        <div 
          className={`h-1.5 rounded-full ${confidence >= 70 ? 'bg-green-500' : confidence >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
          style={{ width: `${confidence}%` }}
        />
      </div>
      <span className={`text-xs font-medium ${getColor()}`}>{confidence}%</span>
    </div>
  )
}

/**
 * 分析师输出卡片
 */
function AnalystCard({ output }: { output: AnalystOutput }) {
  return (
    <div className="border rounded-lg p-3 bg-card">
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-sm">{output.symbol}</span>
        <TrendBadge trend={output.trend} />
      </div>
      <p className="text-sm text-muted-foreground leading-relaxed">{output.summary}</p>
      {output.key_levels && (
        <div className="mt-2 flex gap-4 text-xs text-muted-foreground">
          {output.key_levels.support && (
            <span>Support: ${output.key_levels.support.toFixed(2)}</span>
          )}
          {output.key_levels.resistance && (
            <span>Resistance: ${output.key_levels.resistance.toFixed(2)}</span>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * 交易员建议卡片
 */
function SuggestionCard({ suggestion, variant }: { suggestion: TraderSuggestion; variant: 'bull' | 'bear' }) {
  const borderColor = variant === 'bull' 
    ? 'border-l-green-500' 
    : 'border-l-red-500'
  
  return (
    <div className={`border rounded-lg p-3 bg-card border-l-4 ${borderColor}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="font-medium text-sm">{suggestion.symbol}</span>
        <ConfidenceIndicator confidence={suggestion.confidence} />
      </div>
      <div className="flex items-center gap-2 mb-2">
        <ActionBadge action={suggestion.action} />
        <span className="text-xs text-muted-foreground">
          Alloc: {suggestion.allocation_pct.toFixed(1)}%
        </span>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed">{suggestion.reasoning}</p>
      {suggestion.action !== 'wait' && (
        <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
          <span className="text-red-500">SL: {suggestion.stop_loss_pct}%</span>
          <span className="text-green-500">TP: {suggestion.take_profit_pct}%</span>
        </div>
      )}
    </div>
  )
}

/**
 * 最终决策卡片
 */
function FinalDecisionCard({ decision }: { decision: PortfolioDecision }) {
  const getStatusIcon = () => {
    if (decision.action === 'wait') return <Clock className="h-4 w-4 text-gray-500" />
    if (decision.action.includes('open')) return <Target className="h-4 w-4 text-blue-500" />
    if (decision.action.includes('close')) return <CheckCircle2 className="h-4 w-4 text-green-500" />
    return <AlertTriangle className="h-4 w-4 text-yellow-500" />
  }

  return (
    <div className="flex items-center justify-between border rounded-lg p-3 bg-card hover:bg-accent/50 transition-colors">
      <div className="flex items-center gap-3">
        {getStatusIcon()}
        <div>
          <span className="font-medium text-sm">{decision.symbol}</span>
          <div className="flex items-center gap-2 mt-0.5">
            <ActionBadge action={decision.action} />
            {decision.leverage > 1 && (
              <Badge variant="secondary" className="text-xs">
                {decision.leverage}x
              </Badge>
            )}
          </div>
        </div>
      </div>
      <div className="text-right">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">
            {decision.allocation_pct.toFixed(1)}%
          </span>
          <ConfidenceIndicator confidence={decision.confidence} />
        </div>
        {decision.stop_loss && decision.take_profit && (
          <div className="text-xs text-muted-foreground mt-1">
            <span className="text-red-500">SL: ${decision.stop_loss.toFixed(2)}</span>
            {' / '}
            <span className="text-green-500">TP: ${decision.take_profit.toFixed(2)}</span>
          </div>
        )}
      </div>
    </div>
  )
}

/**
 * 批量决策视图 - 仅显示最终决策（用于非辩论模式）
 */
function BatchDecisionView({ debate }: { debate: DebateResult }) {
  if (!debate.final_decision) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <XCircle className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium mb-2">No Decision Data</h3>
          <p className="text-muted-foreground">
            Wait for the next trading cycle to see AI decisions.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Zap className="h-5 w-5 text-yellow-500" />
          AI Batch Decision
        </h3>
        {debate.completed_at && (
          <span className="text-sm text-muted-foreground flex items-center gap-1">
            <Clock className="h-4 w-4" />
            {new Date(debate.completed_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* 最终决策 */}
      <Card className="border-yellow-200 dark:border-yellow-900/50">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base text-yellow-600 dark:text-yellow-400">
            <Target className="h-5 w-5" />
            Portfolio Decisions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* 汇总指标 */}
            <div className="flex items-center gap-6 text-sm p-3 bg-muted/50 rounded-lg">
              <div>
                <span className="text-muted-foreground">Total Allocation:</span>
                <span className="ml-2 font-semibold">
                  {debate.final_decision.total_allocation_pct?.toFixed(1)}%
                </span>
              </div>
              <div>
                <span className="text-muted-foreground">Cash Reserve:</span>
                <span className="ml-2 font-semibold text-green-600 dark:text-green-400">
                  {debate.final_decision.cash_reserve_pct?.toFixed(1)}%
                </span>
              </div>
            </div>
            
            {/* 决策列表 */}
            <div className="space-y-2">
              {debate.final_decision.decisions?.map((d, idx) => (
                <FinalDecisionCard key={idx} decision={d} />
              ))}
            </div>
            
            {/* 策略说明 */}
            {debate.final_decision.strategy_rationale && (
              <div className="p-3 bg-muted/50 rounded-lg">
                <p className="text-sm">
                  <strong className="text-yellow-600 dark:text-yellow-400">Strategy:</strong>{' '}
                  <span className="text-muted-foreground">
                    {debate.final_decision.strategy_rationale}
                  </span>
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 摘要 */}
      {debate.debate_summary && (
        <div className="text-center text-sm text-muted-foreground p-4 bg-muted/30 rounded-lg">
          {debate.debate_summary}
        </div>
      )}
    </div>
  )
}

/**
 * 获取角色对应的模型名称
 */
function getRoleModelName(
  role: string,
  roleLlmInfo?: Record<string, { id: number; model_name: string; display_name?: string }>
): string | null {
  if (!roleLlmInfo) return null
  const info = roleLlmInfo[role]
  return info?.model_name || null
}

/**
 * 辩论模式视图 - 显示完整的多角色辩论过程
 */
function DebateModeView({ 
  debate, 
  roleLlmInfo 
}: { 
  debate: DebateResult
  roleLlmInfo?: Record<string, { id: number; model_name: string; display_name?: string }>
}) {
  return (
    <div className="space-y-6">
      {/* 时间线头部 */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Shield className="h-5 w-5 text-purple-500" />
          AI Multi-Role Debate
        </h3>
        {debate.completed_at && (
          <span className="text-sm text-muted-foreground flex items-center gap-1">
            <Clock className="h-4 w-4" />
            {new Date(debate.completed_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Phase 1: 市场分析师 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <User className="h-5 w-5 text-blue-500" />
            Phase 1: Market Analyst
            {getRoleModelName('analyst', roleLlmInfo) && (
              <span className="text-xs text-muted-foreground font-normal">
                ({getRoleModelName('analyst', roleLlmInfo)})
              </span>
            )}
            <Badge variant="secondary" className="ml-2">
              {debate.analyst_outputs?.length || 0} reports
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {debate.analyst_outputs && debate.analyst_outputs.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {debate.analyst_outputs.map((output, idx) => (
                <AnalystCard key={idx} output={output} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No analyst reports available</p>
          )}
        </CardContent>
      </Card>

      {/* Phase 2: 多头 vs 空头 */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* 多头建议 */}
        <Card className="border-green-200 dark:border-green-900/50">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-green-600 dark:text-green-400">
              <TrendingUp className="h-5 w-5" />
              Bull Trader
              {getRoleModelName('bull', roleLlmInfo) && (
                <span className="text-xs text-muted-foreground font-normal">
                  ({getRoleModelName('bull', roleLlmInfo)})
                </span>
              )}
              <Badge variant="secondary" className="ml-2 bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                {debate.bull_suggestions?.length || 0} suggestions
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {debate.bull_suggestions && debate.bull_suggestions.length > 0 ? (
              <div className="space-y-3">
                {debate.bull_suggestions.map((s, idx) => (
                  <SuggestionCard key={idx} suggestion={s} variant="bull" />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No bullish suggestions</p>
            )}
          </CardContent>
        </Card>

        {/* 空头建议 */}
        <Card className="border-red-200 dark:border-red-900/50">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base text-red-600 dark:text-red-400">
              <TrendingDown className="h-5 w-5" />
              Bear Trader
              {getRoleModelName('bear', roleLlmInfo) && (
                <span className="text-xs text-muted-foreground font-normal">
                  ({getRoleModelName('bear', roleLlmInfo)})
                </span>
              )}
              <Badge variant="secondary" className="ml-2 bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                {debate.bear_suggestions?.length || 0} suggestions
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {debate.bear_suggestions && debate.bear_suggestions.length > 0 ? (
              <div className="space-y-3">
                {debate.bear_suggestions.map((s, idx) => (
                  <SuggestionCard key={idx} suggestion={s} variant="bear" />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No bearish suggestions</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Phase 3: 最终决策 */}
      <Card className="border-purple-200 dark:border-purple-900/50">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base text-purple-600 dark:text-purple-400">
            <Shield className="h-5 w-5" />
            Phase 3: Risk Manager Final Decision
            {getRoleModelName('risk_manager', roleLlmInfo) && (
              <span className="text-xs text-muted-foreground font-normal">
                ({getRoleModelName('risk_manager', roleLlmInfo)})
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {debate.final_decision ? (
            <div className="space-y-4">
              {/* 汇总指标 */}
              <div className="flex items-center gap-6 text-sm p-3 bg-muted/50 rounded-lg">
                <div>
                  <span className="text-muted-foreground">Total Allocation:</span>
                  <span className="ml-2 font-semibold">
                    {debate.final_decision.total_allocation_pct?.toFixed(1)}%
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">Cash Reserve:</span>
                  <span className="ml-2 font-semibold text-green-600 dark:text-green-400">
                    {debate.final_decision.cash_reserve_pct?.toFixed(1)}%
                  </span>
                </div>
              </div>
              
              {/* 决策列表 */}
              <div className="space-y-2">
                {debate.final_decision.decisions?.map((d, idx) => (
                  <FinalDecisionCard key={idx} decision={d} />
                ))}
              </div>
              
              {/* 策略说明 */}
              {debate.final_decision.strategy_rationale && (
                <div className="p-3 bg-muted/50 rounded-lg">
                  <p className="text-sm">
                    <strong className="text-purple-600 dark:text-purple-400">Strategy:</strong>{' '}
                    <span className="text-muted-foreground">
                      {debate.final_decision.strategy_rationale}
                    </span>
                  </p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No final decision available</p>
          )}
        </CardContent>
      </Card>

      {/* 辩论摘要 */}
      {debate.debate_summary && (
        <div className="text-center text-sm text-muted-foreground p-4 bg-muted/30 rounded-lg">
          {debate.debate_summary}
        </div>
      )}
    </div>
  )
}

/**
 * 主组件 - AI 决策查看器
 */
export function DebateViewer({ debate, isLoading, roleLlmInfo }: DebateViewerProps) {
  // 加载状态
  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader className="pb-3">
              <div className="h-5 bg-muted rounded w-1/4" />
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="h-20 bg-muted rounded" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }
  
  // 无数据状态
  if (!debate) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <XCircle className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium mb-2">No Decision Data Available</h3>
          <p className="text-muted-foreground">
            Start the bot to see AI trading decisions.
          </p>
        </CardContent>
      </Card>
    )
  }

  // 根据数据判断显示模式
  if (isDebateMode(debate)) {
    // 辩论模式 - 显示完整辩论过程
    return <DebateModeView debate={debate} roleLlmInfo={roleLlmInfo} />
  } else {
    // 批量决策模式 - 仅显示最终决策
    return <BatchDecisionView debate={debate} />
  }
}
