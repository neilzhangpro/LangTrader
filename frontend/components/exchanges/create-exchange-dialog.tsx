'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Loader2 } from 'lucide-react'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from '@/components/ui/use-toast'
import * as exchangesApi from '@/lib/api/exchanges'
import type { ExchangeCreateRequest } from '@/types/api'

// 支持的交易所类型
const EXCHANGE_TYPES = [
  { value: 'hyperliquid', label: 'Hyperliquid' },
  { value: 'binance', label: 'Binance' },
  { value: 'okx', label: 'OKX' },
  { value: 'bybit', label: 'Bybit' },
  { value: 'bitget', label: 'Bitget' },
  { value: 'gate', label: 'Gate.io' },
  { value: 'kucoin', label: 'KuCoin' },
]

interface CreateExchangeDialogProps {
  children?: React.ReactNode
}

/**
 * 创建交易所配置的 Dialog 组件
 */
export function CreateExchangeDialog({ children }: CreateExchangeDialogProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  // 表单状态
  const [formData, setFormData] = useState<ExchangeCreateRequest>({
    name: '',
    type: 'hyperliquid',
    apikey: '',
    secretkey: '',
    testnet: false,
    slippage: 0.001,
  })

  // 创建 mutation
  const createMutation = useMutation({
    mutationFn: exchangesApi.createExchange,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exchanges'] })
      toast({
        title: 'Exchange Created',
        description: `Successfully created exchange "${formData.name}"`,
      })
      setOpen(false)
      resetForm()
    },
    onError: (error: Error) => {
      toast({
        title: 'Creation Failed',
        description: error.message || 'Failed to create exchange',
        variant: 'destructive',
      })
    },
  })

  // 重置表单
  const resetForm = () => {
    setFormData({
      name: '',
      type: 'hyperliquid',
      apikey: '',
      secretkey: '',
      testnet: false,
      slippage: 0.001,
    })
  }

  // 提交表单
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name || !formData.apikey || !formData.secretkey) {
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
            Add Exchange
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add Exchange</DialogTitle>
            <DialogDescription>
              Configure a new exchange connection for trading
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* 名称 */}
            <div className="grid gap-2">
              <Label htmlFor="name">Name *</Label>
              <Input
                id="name"
                placeholder="My Hyperliquid Account"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>

            {/* 交易所类型 */}
            <div className="grid gap-2">
              <Label htmlFor="type">Exchange Type *</Label>
              <Select
                value={formData.type}
                onValueChange={(value) => setFormData({ ...formData, type: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select exchange" />
                </SelectTrigger>
                <SelectContent>
                  {EXCHANGE_TYPES.map((ex) => (
                    <SelectItem key={ex.value} value={ex.value}>
                      {ex.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* API Key */}
            <div className="grid gap-2">
              <Label htmlFor="apikey">API Key *</Label>
              <Input
                id="apikey"
                type="password"
                placeholder="Enter your API key"
                value={formData.apikey}
                onChange={(e) => setFormData({ ...formData, apikey: e.target.value })}
              />
            </div>

            {/* Secret Key */}
            <div className="grid gap-2">
              <Label htmlFor="secretkey">Secret Key *</Label>
              <Input
                id="secretkey"
                type="password"
                placeholder="Enter your secret key"
                value={formData.secretkey}
                onChange={(e) => setFormData({ ...formData, secretkey: e.target.value })}
              />
            </div>

            {/* Slippage */}
            <div className="grid gap-2">
              <Label htmlFor="slippage">Slippage (%)</Label>
              <Input
                id="slippage"
                type="number"
                step="0.01"
                min="0"
                max="5"
                placeholder="0.1"
                value={(formData.slippage || 0) * 100}
                onChange={(e) => setFormData({ ...formData, slippage: parseFloat(e.target.value) / 100 })}
              />
            </div>

            {/* Testnet 开关 */}
            <div className="flex items-center justify-between">
              <Label htmlFor="testnet">Use Testnet</Label>
              <Switch
                id="testnet"
                checked={formData.testnet}
                onCheckedChange={(checked) => setFormData({ ...formData, testnet: checked })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create Exchange
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

