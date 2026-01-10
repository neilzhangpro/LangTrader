'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Brain, 
  Plus, 
  Trash2, 
  TestTube, 
  Star,
  RefreshCw,
  CheckCircle
} from 'lucide-react'
import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { toast } from '@/components/ui/use-toast'
import { CreateLLMDialog } from '@/components/llm/create-llm-dialog'
import * as llmConfigsApi from '@/lib/api/llm-configs'

/**
 * LLM 配置页面
 */
export default function LLMConfigsPage() {
  const queryClient = useQueryClient()
  const [testingId, setTestingId] = useState<number | null>(null)

  // 获取 LLM 配置列表
  const { data: configs, isLoading } = useQuery({
    queryKey: ['llm-configs'],
    queryFn: () => llmConfigsApi.listLLMConfigs(),
  })

  // 测试连接
  const testMutation = useMutation({
    mutationFn: async (id: number) => {
      setTestingId(id)
      return llmConfigsApi.testLLMConfig(id)
    },
    onSuccess: (result) => {
      setTestingId(null)
      toast({
        title: result.success ? 'LLM Connection Successful' : 'Connection Failed',
        description: result.success 
          ? `Response: ${result.response_preview?.slice(0, 50)}...`
          : result.message,
        variant: result.success ? 'success' : 'destructive',
      })
    },
    onError: () => {
      setTestingId(null)
      toast({
        title: 'Test Failed',
        description: 'Failed to test LLM connection',
        variant: 'destructive',
      })
    },
  })

  // 设置默认
  const setDefaultMutation = useMutation({
    mutationFn: llmConfigsApi.setDefaultLLMConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-configs'] })
      toast({
        title: 'Default Updated',
        description: 'The default LLM config has been updated',
      })
    },
  })

  // 删除配置
  const deleteMutation = useMutation({
    mutationFn: llmConfigsApi.deleteLLMConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-configs'] })
      toast({
        title: 'Config Deleted',
        description: 'The LLM configuration has been removed',
      })
    },
  })

  // 获取 provider 颜色
  const getProviderColor = (provider: string) => {
    switch (provider) {
      case 'openai': return 'bg-green-500/20 text-green-500'
      case 'anthropic': return 'bg-orange-500/20 text-orange-500'
      case 'azure': return 'bg-blue-500/20 text-blue-500'
      case 'ollama': return 'bg-purple-500/20 text-purple-500'
      default: return 'bg-gray-500/20 text-gray-500'
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">LLM Configurations</h1>
          <p className="text-muted-foreground">
            Manage your LLM providers and API settings
          </p>
        </div>
        <CreateLLMDialog />
      </div>

      {/* 配置列表 */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2].map((i) => (
            <Card key={i} className="h-48 animate-pulse bg-muted" />
          ))}
        </div>
      ) : configs && configs.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {configs.map((config) => (
            <Card key={config.id} className={config.is_default ? 'border-primary' : ''}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="flex items-center gap-2">
                      <Brain className="h-5 w-5" />
                      {config.display_name || config.name}
                      {config.is_default && (
                        <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                      )}
                    </CardTitle>
                    <CardDescription className="mt-1">
                      {config.model_name}
                    </CardDescription>
                    <div className="mt-1 text-xs text-muted-foreground font-mono">
                      ID: {config.id}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getProviderColor(config.provider)}`}>
                      {config.provider}
                    </span>
                    <Badge variant={config.is_enabled ? 'success' : 'secondary'}>
                      {config.is_enabled ? 'Enabled' : 'Disabled'}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* 操作按钮 */}
                <div className="flex gap-2">
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => testMutation.mutate(config.id)}
                    disabled={testingId === config.id}
                  >
                    {testingId === config.id ? (
                      <RefreshCw className="h-4 w-4 mr-1 animate-spin" />
                    ) : (
                      <TestTube className="h-4 w-4 mr-1" />
                    )}
                    Test
                  </Button>
                  {!config.is_default && config.is_enabled && (
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => setDefaultMutation.mutate(config.id)}
                      disabled={setDefaultMutation.isPending}
                    >
                      <Star className="h-4 w-4 mr-1" />
                      Set Default
                    </Button>
                  )}
                  {!config.is_default && (
                    <Button 
                      variant="ghost" 
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => {
                        if (confirm('Are you sure you want to delete this LLM config?')) {
                          deleteMutation.mutate(config.id)
                        }
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card className="p-12 text-center">
          <Brain className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-xl font-medium mb-2">No LLM Configs</h3>
          <p className="text-muted-foreground mb-4">
            Add your first LLM configuration to enable AI trading
          </p>
          <CreateLLMDialog>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Add LLM Config
            </Button>
          </CreateLLMDialog>
        </Card>
      )}
    </div>
  )
}

