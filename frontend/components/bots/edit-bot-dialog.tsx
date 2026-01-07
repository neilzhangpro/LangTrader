'use client'

import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Edit, Loader2 } from 'lucide-react'
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
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from '@/components/ui/use-toast'
import * as botsApi from '@/lib/api/bots'
import * as exchangesApi from '@/lib/api/exchanges'
import * as workflowsApi from '@/lib/api/workflows'
import * as llmConfigsApi from '@/lib/api/llm-configs'
import type { BotDetail, BotUpdateRequest } from '@/types/api'

interface EditBotDialogProps {
  bot: BotDetail
  children?: React.ReactNode
}

/**
 * 编辑 Bot 的 Dialog 组件
 */
export function EditBotDialog({ bot, children }: EditBotDialogProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  // 表单状态
  const [displayName, setDisplayName] = useState(bot.display_name || '')
  const [description, setDescription] = useState(bot.description || '')
  const [tradingMode, setTradingMode] = useState(bot.trading_mode)
  const [exchangeId, setExchangeId] = useState(bot.exchange_id.toString())
  const [workflowId, setWorkflowId] = useState(bot.workflow_id.toString())
  const [llmId, setLlmId] = useState(bot.llm_id?.toString() || 'none')
  const [isActive, setIsActive] = useState(bot.is_active)
  const [maxLeverage, setMaxLeverage] = useState((bot.max_leverage ?? 3).toString())
  const [cycleInterval, setCycleInterval] = useState((bot.cycle_interval_seconds ?? 180).toString())
  const [maxSymbols, setMaxSymbols] = useState((bot.max_concurrent_symbols ?? 5).toString())
  const [quantThreshold, setQuantThreshold] = useState((bot.quant_signal_threshold ?? 50).toString())

  // 重置表单到当前 Bot 值
  useEffect(() => {
    if (open) {
      setDisplayName(bot.display_name || '')
      setDescription(bot.description || '')
      setTradingMode(bot.trading_mode)
      setExchangeId(bot.exchange_id.toString())
      setWorkflowId(bot.workflow_id.toString())
      setLlmId(bot.llm_id?.toString() || 'none')
      setIsActive(bot.is_active)
      setMaxLeverage((bot.max_leverage ?? 3).toString())
      setCycleInterval((bot.cycle_interval_seconds ?? 180).toString())
      setMaxSymbols((bot.max_concurrent_symbols ?? 5).toString())
      setQuantThreshold((bot.quant_signal_threshold ?? 50).toString())
    }
  }, [open, bot])

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
    queryFn: () => llmConfigsApi.listLLMConfigs(),
    enabled: open,
  })

  // 更新 mutation
  const updateMutation = useMutation({
    mutationFn: (data: BotUpdateRequest) => botsApi.updateBot(bot.id, data),
    onSuccess: () => {
      toast({
        title: 'Bot Updated',
        description: 'Bot configuration has been updated successfully.',
      })
      queryClient.invalidateQueries({ queryKey: ['bot', bot.id] })
      queryClient.invalidateQueries({ queryKey: ['bots'] })
      setOpen(false)
    },
    onError: (error: Error) => {
      toast({
        title: 'Error',
        description: error.message || 'Failed to update bot',
        variant: 'destructive',
      })
    },
  })

  // 提交表单
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    const updateData: BotUpdateRequest = {
      display_name: displayName || undefined,
      description: description || undefined,
      trading_mode: tradingMode,
      exchange_id: parseInt(exchangeId),
      workflow_id: parseInt(workflowId),
      llm_id: llmId && llmId !== 'none' ? parseInt(llmId) : undefined,
      is_active: isActive,
      max_leverage: parseInt(maxLeverage),
      cycle_interval_seconds: parseInt(cycleInterval),
      max_concurrent_symbols: parseInt(maxSymbols),
      quant_signal_threshold: parseInt(quantThreshold),
    }

    updateMutation.mutate(updateData)
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children || (
          <Button variant="outline">
            <Edit className="h-4 w-4 mr-2" />
            Edit Bot
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Edit Bot: {bot.display_name || bot.name}</DialogTitle>
            <DialogDescription>
              Update the bot configuration. Changes will take effect on next cycle.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* 基本信息 */}
            <div className="grid gap-2">
              <Label htmlFor="displayName">Display Name</Label>
              <Input
                id="displayName"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="e.g. My Trading Bot"
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this bot does..."
                rows={2}
              />
            </div>

            {/* 交易模式和状态 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Trading Mode</Label>
                <Select value={tradingMode} onValueChange={(v) => setTradingMode(v as 'paper' | 'live')}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="paper">Paper Trading</SelectItem>
                    <SelectItem value="live">Live Trading</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between p-3 border rounded-md">
                <Label htmlFor="isActive" className="cursor-pointer">Active</Label>
                <Switch
                  id="isActive"
                  checked={isActive}
                  onCheckedChange={setIsActive}
                />
              </div>
            </div>

            {/* 关联配置 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Exchange</Label>
                <Select value={exchangeId} onValueChange={setExchangeId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select exchange" />
                  </SelectTrigger>
                  <SelectContent>
                    {exchanges?.map((ex) => (
                      <SelectItem key={ex.id} value={ex.id.toString()}>
                        {ex.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid gap-2">
                <Label>Workflow</Label>
                <Select value={workflowId} onValueChange={setWorkflowId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select workflow" />
                  </SelectTrigger>
                  <SelectContent>
                    {workflows?.map((wf) => (
                      <SelectItem key={wf.id} value={wf.id.toString()}>
                        {wf.display_name || wf.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-2">
              <Label>LLM Config</Label>
              <Select value={llmId} onValueChange={setLlmId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select LLM (optional)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  {llmConfigs?.map((llm) => (
                    <SelectItem key={llm.id} value={llm.id.toString()}>
                      {llm.display_name || llm.name} ({llm.provider})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 交易参数 */}
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Max Leverage</Label>
                <Input
                  type="number"
                  value={maxLeverage}
                  onChange={(e) => setMaxLeverage(e.target.value)}
                  min={1}
                  max={100}
                />
              </div>

              <div className="grid gap-2">
                <Label>Cycle Interval (seconds)</Label>
                <Input
                  type="number"
                  value={cycleInterval}
                  onChange={(e) => setCycleInterval(e.target.value)}
                  min={60}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label>Max Concurrent Symbols</Label>
                <Input
                  type="number"
                  value={maxSymbols}
                  onChange={(e) => setMaxSymbols(e.target.value)}
                  min={1}
                  max={50}
                />
              </div>

              <div className="grid gap-2">
                <Label>Quant Signal Threshold</Label>
                <Input
                  type="number"
                  value={quantThreshold}
                  onChange={(e) => setQuantThreshold(e.target.value)}
                  min={0}
                  max={100}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

