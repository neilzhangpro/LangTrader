'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  ArrowLeftRight, 
  Plus, 
  Trash2, 
  TestTube, 
  CheckCircle, 
  XCircle,
  Wallet,
  RefreshCw
} from 'lucide-react'
import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/components/ui/use-toast'
import { formatCurrency } from '@/lib/utils'
import { CreateExchangeDialog } from '@/components/exchanges/create-exchange-dialog'
import * as exchangesApi from '@/lib/api/exchanges'

/**
 * 交易所配置页面
 */
export default function ExchangesPage() {
  const queryClient = useQueryClient()
  const [testingId, setTestingId] = useState<number | null>(null)

  // 获取交易所列表
  const { data: exchanges, isLoading } = useQuery({
    queryKey: ['exchanges'],
    queryFn: exchangesApi.listExchanges,
  })

  // 测试连接
  const testMutation = useMutation({
    mutationFn: async (id: number) => {
      setTestingId(id)
      return exchangesApi.testExchange(id)
    },
    onSuccess: (result, id) => {
      setTestingId(null)
      toast({
        title: result.success ? 'Connection Successful' : 'Connection Failed',
        description: result.success 
          ? `Latency: ${result.latency_ms}ms`
          : result.message,
        variant: result.success ? 'success' : 'destructive',
      })
    },
    onError: () => {
      setTestingId(null)
      toast({
        title: 'Test Failed',
        description: 'Failed to test connection',
        variant: 'destructive',
      })
    },
  })

  // 删除交易所
  const deleteMutation = useMutation({
    mutationFn: exchangesApi.deleteExchange,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exchanges'] })
      toast({
        title: 'Exchange Deleted',
        description: 'The exchange configuration has been removed',
      })
    },
  })

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Exchanges</h1>
          <p className="text-muted-foreground">
            Manage your exchange API configurations
          </p>
        </div>
        <CreateExchangeDialog />
      </div>

      {/* 交易所列表 */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2].map((i) => (
            <Card key={i} className="h-48 animate-pulse bg-muted" />
          ))}
        </div>
      ) : exchanges && exchanges.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {exchanges.map((exchange) => (
            <Card key={exchange.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <ArrowLeftRight className="h-5 w-5" />
                      {exchange.name}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {exchange.type}
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    {exchange.testnet && (
                      <Badge variant="warning">Testnet</Badge>
                    )}
                    <Badge variant={exchange.has_api_key ? 'success' : 'error'}>
                      {exchange.has_api_key ? 'Configured' : 'No API Key'}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 状态 */}
                <div className="flex items-center gap-4 text-sm">
                  <div className="flex items-center gap-1">
                    {exchange.has_api_key ? (
                      <CheckCircle className="h-4 w-4 text-profit" />
                    ) : (
                      <XCircle className="h-4 w-4 text-loss" />
                    )}
                    <span className="text-muted-foreground">API Key</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {exchange.has_secret_key ? (
                      <CheckCircle className="h-4 w-4 text-profit" />
                    ) : (
                      <XCircle className="h-4 w-4 text-loss" />
                    )}
                    <span className="text-muted-foreground">Secret Key</span>
                  </div>
                </div>

                {/* 操作按钮 */}
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => testMutation.mutate(exchange.id)}
                    disabled={testingId === exchange.id}
                  >
                    {testingId === exchange.id ? (
                      <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <TestTube className="h-4 w-4 mr-1" />
                    )}
                    Test
                  </Button>
                  <Button 
                    variant="outline" 
                    size="sm"
                    disabled
                  >
                    <Wallet className="h-4 w-4 mr-1" />
                    Balance
                  </Button>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => {
                      if (confirm('Are you sure you want to delete this exchange?')) {
                        deleteMutation.mutate(exchange.id)
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="p-12 text-center">
          <ArrowLeftRight className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-xl font-medium mb-2">No Exchanges Configured</h3>
          <p className="text-muted-foreground mb-4">
            Add your first exchange to start trading
          </p>
          <CreateExchangeDialog>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Add Exchange
            </Button>
          </CreateExchangeDialog>
        </Card>
      )}
    </div>
  )
}

