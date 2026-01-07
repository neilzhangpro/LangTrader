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
import * as llmConfigsApi from '@/lib/api/llm-configs'
import type { LLMConfigCreateRequest } from '@/types/api'

// LLM 提供商
const LLM_PROVIDERS = [
  { value: 'openai', label: 'OpenAI', requiresApiKey: true },
  { value: 'anthropic', label: 'Anthropic', requiresApiKey: true },
  { value: 'azure', label: 'Azure OpenAI', requiresApiKey: true },
  { value: 'ollama', label: 'Ollama (Local)', requiresApiKey: false },
]

// 常用模型
const COMMON_MODELS: Record<string, string[]> = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  anthropic: ['claude-3-5-sonnet-20241022', 'claude-3-opus-20240229', 'claude-3-haiku-20240307'],
  azure: ['gpt-4o', 'gpt-4', 'gpt-35-turbo'],
  ollama: ['llama3', 'mistral', 'codellama', 'qwen2'],
}

interface CreateLLMDialogProps {
  children?: React.ReactNode
}

/**
 * 创建 LLM 配置的 Dialog 组件
 */
export function CreateLLMDialog({ children }: CreateLLMDialogProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()

  // 表单状态
  const [formData, setFormData] = useState<LLMConfigCreateRequest>({
    name: '',
    provider: 'openai',
    model_name: 'gpt-4o-mini',
    api_key: '',
    base_url: '',
    temperature: 0.7,
    max_retries: 3,
    is_enabled: true,
  })

  // 获取当前提供商配置
  const currentProvider = LLM_PROVIDERS.find(p => p.value === formData.provider)

  // 创建 mutation
  const createMutation = useMutation({
    mutationFn: llmConfigsApi.createLLMConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-configs'] })
      toast({
        title: 'LLM Config Created',
        description: `Successfully created LLM config "${formData.name}"`,
      })
      setOpen(false)
      resetForm()
    },
    onError: (error: Error) => {
      toast({
        title: 'Creation Failed',
        description: error.message || 'Failed to create LLM config',
        variant: 'destructive',
      })
    },
  })

  // 重置表单
  const resetForm = () => {
    setFormData({
      name: '',
      provider: 'openai',
      model_name: 'gpt-4o-mini',
      api_key: '',
      base_url: '',
      temperature: 0.7,
      max_retries: 3,
      is_enabled: true,
    })
  }

  // 切换提供商时更新默认模型
  const handleProviderChange = (provider: string) => {
    const models = COMMON_MODELS[provider] || []
    setFormData({
      ...formData,
      provider,
      model_name: models[0] || '',
      // Ollama 默认使用 localhost
      base_url: provider === 'ollama' ? 'http://localhost:11434' : '',
    })
  }

  // 提交表单
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name || !formData.model_name) {
      toast({
        title: 'Validation Error',
        description: 'Please fill in all required fields',
        variant: 'destructive',
      })
      return
    }
    if (currentProvider?.requiresApiKey && !formData.api_key) {
      toast({
        title: 'Validation Error',
        description: 'API Key is required for this provider',
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
            Add LLM Config
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Add LLM Configuration</DialogTitle>
            <DialogDescription>
              Configure a new LLM provider for AI-powered trading decisions
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* 配置名称 */}
            <div className="grid gap-2">
              <Label htmlFor="name">Config Name *</Label>
              <Input
                id="name"
                placeholder="My OpenAI Config"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              />
            </div>

            {/* 提供商 */}
            <div className="grid gap-2">
              <Label htmlFor="provider">Provider *</Label>
              <Select
                value={formData.provider}
                onValueChange={handleProviderChange}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select provider" />
                </SelectTrigger>
                <SelectContent>
                  {LLM_PROVIDERS.map((p) => (
                    <SelectItem key={p.value} value={p.value}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 模型名称 */}
            <div className="grid gap-2">
              <Label htmlFor="model_name">Model Name *</Label>
              <Select
                value={formData.model_name}
                onValueChange={(value) => setFormData({ ...formData, model_name: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  {(COMMON_MODELS[formData.provider] || []).map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Or type a custom model name directly
              </p>
            </div>

            {/* API Key (非 Ollama) */}
            {currentProvider?.requiresApiKey && (
              <div className="grid gap-2">
                <Label htmlFor="api_key">API Key *</Label>
                <Input
                  id="api_key"
                  type="password"
                  placeholder="sk-..."
                  value={formData.api_key}
                  onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                />
              </div>
            )}

            {/* Base URL */}
            <div className="grid gap-2">
              <Label htmlFor="base_url">Base URL (Optional)</Label>
              <Input
                id="base_url"
                placeholder={formData.provider === 'ollama' ? 'http://localhost:11434' : 'https://api.openai.com/v1'}
                value={formData.base_url}
                onChange={(e) => setFormData({ ...formData, base_url: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                Leave empty to use the default API endpoint
              </p>
            </div>

            {/* Temperature */}
            <div className="grid gap-2">
              <Label htmlFor="temperature">Temperature: {formData.temperature}</Label>
              <Input
                id="temperature"
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={formData.temperature}
                onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                className="cursor-pointer"
              />
              <p className="text-xs text-muted-foreground">
                Lower = more deterministic, Higher = more creative
              </p>
            </div>

            {/* 启用开关 */}
            <div className="flex items-center justify-between">
              <Label htmlFor="is_enabled">Enable this config</Label>
              <Switch
                id="is_enabled"
                checked={formData.is_enabled}
                onCheckedChange={(checked) => setFormData({ ...formData, is_enabled: checked })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create LLM Config
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

