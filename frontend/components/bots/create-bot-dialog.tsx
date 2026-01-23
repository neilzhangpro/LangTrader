'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Loader2, ChevronDown, ChevronRight } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible'
import { toast } from '@/components/ui/use-toast'
import * as botsApi from '@/lib/api/bots'
import * as exchangesApi from '@/lib/api/exchanges'
import * as workflowsApi from '@/lib/api/workflows'
import * as llmConfigsApi from '@/lib/api/llm-configs'
import type { BotCreateRequest } from '@/types/api'

// 默认 JSON 配置值
const DEFAULT_QUANT_SIGNAL_WEIGHTS = {
  trend: 0.4,
  momentum: 0.3,
  volume: 0.2,
  sentiment: 0.1
}

const DEFAULT_TRADING_TIMEFRAMES = ["3m", "4h"]

const DEFAULT_OHLCV_LIMITS = {
  "3m": 100,
  "4h": 100
}

const DEFAULT_RISK_LIMITS = {
  max_total_exposure_pct: 0.8,
  max_single_symbol_pct: 0.3,
  max_leverage: 10,
  max_consecutive_losses: 5,
  max_daily_loss_pct: 0.05,
  max_drawdown_pct: 0.15,
  max_funding_rate_pct: 0.001,
  funding_rate_check_enabled: true,
  min_position_size_usd: 10.0,
  max_position_size_usd: 10000.0,
  min_risk_reward_ratio: 2.0,
  hard_stop_enabled: true,
  pause_on_consecutive_loss: true,
  pause_on_max_drawdown: true,
  // 追踪止损配置
  trailing_stop_enabled: false,        // 是否启用追踪止损（默认关闭）
  trailing_stop_trigger_pct: 3.0,      // 触发追踪的最小盈利 (3%)
  trailing_stop_distance_pct: 1.5,     // 追踪距离 (1.5%)
  trailing_stop_lock_profit_pct: 1.0   // 最少锁定利润 (1%)
}

const DEFAULT_INDICATOR_CONFIGS = {
  ema_periods: [20, 50, 200],
  rsi_period: 7,
  macd_config: { fast: 12, slow: 26, signal: 9 },
  atr_period: 14,
  bollinger_period: 20,
  bollinger_std: 2.0,
  stochastic_k: 14,
  stochastic_d: 3
}

interface CreateBotDialogProps {
  children?: React.ReactNode
}

/**
 * 创建 Bot 的 Dialog 组件
 */
export function CreateBotDialog({ children }: CreateBotDialogProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  // 预加载依赖数据
  const { data: exchanges } = useQuery({
    queryKey: ['exchanges'],
    queryFn: exchangesApi.listExchanges,
    enabled: open,
  })

  const { data: workflows } = useQuery({
    queryKey: ['workflows'],
    queryFn: workflowsApi.listWorkflows,
    enabled: open,
  })

  const { data: llmConfigs } = useQuery({
    queryKey: ['llm-configs'],
    queryFn: () => llmConfigsApi.listLLMConfigs(true),
    enabled: open,
  })

  // 高级配置折叠状态
  const [advancedJsonOpen, setAdvancedJsonOpen] = useState(false)

  // JSON 字段的字符串状态（用于编辑）
  const [jsonFields, setJsonFields] = useState({
    quant_signal_weights: JSON.stringify(DEFAULT_QUANT_SIGNAL_WEIGHTS, null, 2),
    trading_timeframes: JSON.stringify(DEFAULT_TRADING_TIMEFRAMES, null, 2),
    ohlcv_limits: JSON.stringify(DEFAULT_OHLCV_LIMITS, null, 2),
    risk_limits: JSON.stringify(DEFAULT_RISK_LIMITS, null, 2),
    indicator_configs: JSON.stringify(DEFAULT_INDICATOR_CONFIGS, null, 2),
  })

  // JSON 验证错误状态
  const [jsonErrors, setJsonErrors] = useState<Record<string, string>>({})

  // 表单状态
  const [formData, setFormData] = useState<BotCreateRequest>({
    name: '',
    display_name: '',
    description: '',
    prompt: 'default.txt',
    exchange_id: 0,
    workflow_id: 0,
    llm_id: undefined,
    trading_mode: 'paper',
    // Tracing config
    enable_tracing: true,
    tracing_project: 'langtrader_pro',
    tracing_key: '',
    // Agent search key
    tavily_search_key: '',
    // Trading params
    max_leverage: 3,
    max_concurrent_symbols: 5,
    cycle_interval_seconds: 180,
    quant_signal_threshold: 45,  // 百分制 0-100
    // Dynamic config (使用默认值)
    quant_signal_weights: DEFAULT_QUANT_SIGNAL_WEIGHTS,
    trading_timeframes: DEFAULT_TRADING_TIMEFRAMES,
    ohlcv_limits: DEFAULT_OHLCV_LIMITS,
    risk_limits: DEFAULT_RISK_LIMITS,
    indicator_configs: DEFAULT_INDICATOR_CONFIGS,
    // Balance
    initial_balance: undefined,
  })

  // 创建 mutation
  const createMutation = useMutation({
    mutationFn: botsApi.createBot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bots'] })
      toast({
        title: 'Bot Created',
        description: `Successfully created bot "${formData.display_name || formData.name}"`,
      })
      setOpen(false)
      resetForm()
    },
    onError: (error: Error) => {
      toast({
        title: 'Creation Failed',
        description: error.message || 'Failed to create bot',
        variant: 'destructive',
      })
    },
  })

  // 验证并更新 JSON 字段
  const handleJsonChange = (field: keyof typeof jsonFields, value: string) => {
    setJsonFields(prev => ({ ...prev, [field]: value }))
    
    try {
      const parsed = JSON.parse(value)
      setJsonErrors(prev => ({ ...prev, [field]: '' }))
      setFormData(prev => ({ ...prev, [field]: parsed }))
    } catch {
      setJsonErrors(prev => ({ ...prev, [field]: 'JSON 格式无效' }))
    }
  }

  // 重置表单
  const resetForm = () => {
    setFormData({
      name: '',
      display_name: '',
      description: '',
      prompt: 'default.txt',
      exchange_id: 0,
      workflow_id: 0,
      llm_id: undefined,
      trading_mode: 'paper',
      // Tracing config
      enable_tracing: true,
      tracing_project: 'langtrader_pro',
      tracing_key: '',
      // Agent search key
      tavily_search_key: '',
      // Trading params
      max_leverage: 3,
      max_concurrent_symbols: 5,
      cycle_interval_seconds: 180,
      quant_signal_threshold: 45,  // 百分制 0-100
      // Dynamic config (使用默认值)
      quant_signal_weights: DEFAULT_QUANT_SIGNAL_WEIGHTS,
      trading_timeframes: DEFAULT_TRADING_TIMEFRAMES,
      ohlcv_limits: DEFAULT_OHLCV_LIMITS,
      risk_limits: DEFAULT_RISK_LIMITS,
      indicator_configs: DEFAULT_INDICATOR_CONFIGS,
      // Balance
      initial_balance: undefined,
    })
    setJsonFields({
      quant_signal_weights: JSON.stringify(DEFAULT_QUANT_SIGNAL_WEIGHTS, null, 2),
      trading_timeframes: JSON.stringify(DEFAULT_TRADING_TIMEFRAMES, null, 2),
      ohlcv_limits: JSON.stringify(DEFAULT_OHLCV_LIMITS, null, 2),
      risk_limits: JSON.stringify(DEFAULT_RISK_LIMITS, null, 2),
      indicator_configs: JSON.stringify(DEFAULT_INDICATOR_CONFIGS, null, 2),
    })
    setJsonErrors({})
    setAdvancedJsonOpen(false)
  }

  // 提交表单
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name || !formData.exchange_id || !formData.workflow_id) {
      toast({
        title: 'Validation Error',
        description: 'Please fill in all required fields',
        variant: 'destructive',
      })
      return
    }
    createMutation.mutate(formData)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children || (
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Create Bot
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create Trading Bot</DialogTitle>
            <DialogDescription>
              Configure a new trading bot with exchange, workflow, and LLM settings
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* 基础信息 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="name">Bot Name *</Label>
                <Input
                  id="name"
                  placeholder="my-trading-bot"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value.toLowerCase().replace(/\s+/g, '-') })}
                />
                <p className="text-xs text-muted-foreground">
                  Lowercase, no spaces
                </p>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="display_name">Display Name</Label>
                <Input
                  id="display_name"
                  placeholder="My Trading Bot"
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                />
              </div>
            </div>

            {/* 描述 */}
            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Input
                id="description"
                placeholder="A brief description of this bot..."
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              />
            </div>

            {/* 交易所选择 */}
            <div className="grid gap-2">
              <Label htmlFor="exchange_id">Exchange *</Label>
              <Select
                value={formData.exchange_id ? String(formData.exchange_id) : ''}
                onValueChange={(value) => setFormData({ ...formData, exchange_id: parseInt(value) })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select exchange" />
                </SelectTrigger>
                <SelectContent>
                  {exchanges?.map((ex) => (
                    <SelectItem key={ex.id} value={String(ex.id)}>
                      {ex.name} ({ex.type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {(!exchanges || exchanges.length === 0) && (
                <p className="text-xs text-muted-foreground">
                  No exchanges configured. Please add an exchange first.
                </p>
              )}
            </div>

            {/* 工作流选择 */}
            <div className="grid gap-2">
              <Label htmlFor="workflow_id">Workflow *</Label>
              <Select
                value={formData.workflow_id ? String(formData.workflow_id) : ''}
                onValueChange={(value) => setFormData({ ...formData, workflow_id: parseInt(value) })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select workflow" />
                </SelectTrigger>
                <SelectContent>
                  {workflows?.map((wf) => (
                    <SelectItem key={wf.id} value={String(wf.id)}>
                      {wf.display_name || wf.name} (v{wf.version})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* LLM 配置选择 */}
            <div className="grid gap-2">
              <Label htmlFor="llm_id">LLM Config</Label>
              <Select
                value={formData.llm_id ? String(formData.llm_id) : 'default'}
                onValueChange={(value) => setFormData({ 
                  ...formData, 
                  llm_id: value === 'default' ? undefined : parseInt(value) 
                })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Use default LLM" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">Use Default LLM</SelectItem>
                  {llmConfigs?.map((llm) => (
                    <SelectItem key={llm.id} value={String(llm.id)}>
                      {llm.display_name || llm.name} ({llm.provider})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 交易模式 */}
            <div className="grid gap-2">
              <Label htmlFor="trading_mode">Trading Mode *</Label>
              <Select
                value={formData.trading_mode}
                onValueChange={(value: 'paper' | 'live' | 'backtest') => setFormData({ ...formData, trading_mode: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="paper">Paper Trading (Simulation)</SelectItem>
                  <SelectItem value="live">Live Trading (Real Money)</SelectItem>
                  <SelectItem value="backtest">Backtesting</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Prompt 配置 */}
            <div className="grid gap-2">
              <Label htmlFor="prompt">Prompt Template</Label>
              <Input
                id="prompt"
                placeholder="default.txt"
                value={formData.prompt}
                onChange={(e) => setFormData({ ...formData, prompt: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                决策提示词模板文件名 (位于 prompts/ 目录下)
              </p>
            </div>

            {/* 高级配置 */}
            <div className="border-t pt-4 mt-2">
              <h4 className="text-sm font-medium mb-4">Advanced Settings</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="max_leverage">Max Leverage</Label>
                  <Input
                    id="max_leverage"
                    type="number"
                    min="1"
                    max="100"
                    value={formData.max_leverage}
                    onChange={(e) => setFormData({ ...formData, max_leverage: parseInt(e.target.value) })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="max_concurrent_symbols">Max Symbols</Label>
                  <Input
                    id="max_concurrent_symbols"
                    type="number"
                    min="1"
                    max="50"
                    value={formData.max_concurrent_symbols}
                    onChange={(e) => setFormData({ ...formData, max_concurrent_symbols: parseInt(e.target.value) })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="cycle_interval_seconds">Cycle Interval (s)</Label>
                  <Input
                    id="cycle_interval_seconds"
                    type="number"
                    min="60"
                    max="3600"
                    step="30"
                    value={formData.cycle_interval_seconds}
                    onChange={(e) => setFormData({ ...formData, cycle_interval_seconds: parseInt(e.target.value) })}
                  />
                </div>
              </div>
            </div>

            {/* Tracing 配置 */}
            <div className="border-t pt-4 mt-2">
              <h4 className="text-sm font-medium mb-4">Tracing & Agent Keys</h4>
              <div className="grid gap-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="enable_tracing">启用 LangSmith 追踪</Label>
                  <Switch
                    id="enable_tracing"
                    checked={formData.enable_tracing}
                    onCheckedChange={(checked) => setFormData({ ...formData, enable_tracing: checked })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="tracing_project">LangSmith Project</Label>
                  <Input
                    id="tracing_project"
                    placeholder="langtrader_pro"
                    value={formData.tracing_project}
                    onChange={(e) => setFormData({ ...formData, tracing_project: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    LangSmith 追踪项目名称
                  </p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="tracing_key">LangSmith API Key</Label>
                  <Input
                    id="tracing_key"
                    type="password"
                    placeholder="lsv2_pt_..."
                    value={formData.tracing_key}
                    onChange={(e) => setFormData({ ...formData, tracing_key: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    LangSmith API Key (可选，留空使用环境变量)
                  </p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="tavily_search_key">Tavily Search API Key</Label>
                  <Input
                    id="tavily_search_key"
                    type="password"
                    placeholder="tvly-..."
                    value={formData.tavily_search_key}
                    onChange={(e) => setFormData({ ...formData, tavily_search_key: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    Tavily 搜索 API Key (用于 Agent 搜索功能)
                  </p>
                </div>
              </div>
            </div>

            {/* 资金配置 */}
            <div className="border-t pt-4 mt-2">
              <h4 className="text-sm font-medium mb-4">资金配置</h4>
              <div className="grid gap-2">
                <Label htmlFor="initial_balance">初始余额 (USD)</Label>
                <Input
                  id="initial_balance"
                  type="number"
                  min="0"
                  step="100"
                  placeholder="可选，留空自动获取"
                  value={formData.initial_balance || ''}
                  onChange={(e) => setFormData({ 
                    ...formData, 
                    initial_balance: e.target.value ? parseFloat(e.target.value) : undefined 
                  })}
                />
                <p className="text-xs text-muted-foreground">
                  用于计算盈亏百分比，留空则从交易所获取
                </p>
              </div>
            </div>

            {/* 高级 JSON 配置 */}
            <Collapsible open={advancedJsonOpen} onOpenChange={setAdvancedJsonOpen}>
              <div className="border-t pt-4 mt-2">
                <CollapsibleTrigger asChild>
                  <Button variant="ghost" className="flex w-full justify-between p-0 h-auto">
                    <h4 className="text-sm font-medium">高级 JSON 配置</h4>
                    {advancedJsonOpen ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="space-y-4 mt-4">
                  {/* 量化信号权重 */}
                  <div className="grid gap-2">
                    <Label htmlFor="quant_signal_weights">量化信号权重 (quant_signal_weights)</Label>
                    <Textarea
                      id="quant_signal_weights"
                      className="font-mono text-xs"
                      rows={5}
                      value={jsonFields.quant_signal_weights}
                      onChange={(e) => handleJsonChange('quant_signal_weights', e.target.value)}
                    />
                    {jsonErrors.quant_signal_weights && (
                      <p className="text-xs text-destructive">{jsonErrors.quant_signal_weights}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      各指标权重，总和应为 1.0
                    </p>
                  </div>

                  {/* 交易时间框架 */}
                  <div className="grid gap-2">
                    <Label htmlFor="trading_timeframes">交易时间框架 (trading_timeframes)</Label>
                    <Textarea
                      id="trading_timeframes"
                      className="font-mono text-xs"
                      rows={3}
                      value={jsonFields.trading_timeframes}
                      onChange={(e) => handleJsonChange('trading_timeframes', e.target.value)}
                    />
                    {jsonErrors.trading_timeframes && (
                      <p className="text-xs text-destructive">{jsonErrors.trading_timeframes}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      K 线时间周期，如 [&quot;3m&quot;, &quot;4h&quot;, &quot;1d&quot;]
                    </p>
                  </div>

                  {/* OHLCV 数据量限制 */}
                  <div className="grid gap-2">
                    <Label htmlFor="ohlcv_limits">K 线数据量 (ohlcv_limits)</Label>
                    <Textarea
                      id="ohlcv_limits"
                      className="font-mono text-xs"
                      rows={4}
                      value={jsonFields.ohlcv_limits}
                      onChange={(e) => handleJsonChange('ohlcv_limits', e.target.value)}
                    />
                    {jsonErrors.ohlcv_limits && (
                      <p className="text-xs text-destructive">{jsonErrors.ohlcv_limits}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      每个时间周期获取的 K 线数量
                    </p>
                  </div>

                  {/* 风控配置 */}
                  <div className="grid gap-2">
                    <Label htmlFor="risk_limits">风控配置 (risk_limits)</Label>
                    <Textarea
                      id="risk_limits"
                      className="font-mono text-xs"
                      rows={14}
                      value={jsonFields.risk_limits}
                      onChange={(e) => handleJsonChange('risk_limits', e.target.value)}
                    />
                    {jsonErrors.risk_limits && (
                      <p className="text-xs text-destructive">{jsonErrors.risk_limits}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      仓位控制、风险控制、订单约束、追踪止损等硬性限制。启用 trailing_stop_enabled 可自动移动止损位锁定利润。
                    </p>
                  </div>

                  {/* 指标配置 */}
                  <div className="grid gap-2">
                    <Label htmlFor="indicator_configs">技术指标配置 (indicator_configs)</Label>
                    <Textarea
                      id="indicator_configs"
                      className="font-mono text-xs"
                      rows={8}
                      value={jsonFields.indicator_configs}
                      onChange={(e) => handleJsonChange('indicator_configs', e.target.value)}
                    />
                    {jsonErrors.indicator_configs && (
                      <p className="text-xs text-destructive">{jsonErrors.indicator_configs}</p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      EMA、RSI、MACD、布林带等技术指标参数
                    </p>
                  </div>
                </CollapsibleContent>
              </div>
            </Collapsible>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create Bot
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

