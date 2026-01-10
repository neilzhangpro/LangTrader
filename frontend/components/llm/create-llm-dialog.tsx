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
import { toast } from '@/components/ui/use-toast'
import * as llmConfigsApi from '@/lib/api/llm-configs'
import type { LLMConfigCreateRequest } from '@/types/api'

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
    provider: '',
    model_name: '',
    api_key: '',
    base_url: '',
    temperature: 0.7,
    max_retries: 3,
    is_enabled: true,
  })

  // 判断是否需要API Key（根据provider判断）
  const requiresApiKey = formData.provider && formData.provider !== 'ollama'

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
      provider: '',
      model_name: '',
      api_key: '',
      base_url: '',
      temperature: 0.7,
      max_retries: 3,
      is_enabled: true,
    })
  }

  // Provider 变化时更新 base_url 提示
  const handleProviderChange = (provider: string) => {
    const newFormData = { ...formData, provider }
    if (provider === 'ollama' && !newFormData.base_url) {
      newFormData.base_url = 'http://localhost:11434'
    }
    setFormData(newFormData)
  }

  // 提交表单
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name || !formData.provider || !formData.model_name) {
      toast({
        title: 'Validation Error',
        description: 'Please fill in all required fields (Name, Provider, Model Name)',
        variant: 'destructive',
      })
      return
    }
    if (requiresApiKey && !formData.api_key) {
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
              <Input
                id="provider"
                placeholder="e.g., openai, anthropic, azure, ollama"
                value={formData.provider}
                onChange={(e) => handleProviderChange(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                常用值: openai, anthropic, azure, ollama
              </p>
            </div>

            {/* 模型名称 */}
            <div className="grid gap-2">
              <Label htmlFor="model_name">Model Name *</Label>
              <Input
                id="model_name"
                placeholder="e.g., gpt-4o, claude-3-5-sonnet-20241022, llama3"
                value={formData.model_name}
                onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                输入模型名称，如: gpt-4o, claude-3-5-sonnet-20241022, llama3 等
              </p>
            </div>

            {/* API Key (非 Ollama) */}
            {requiresApiKey && (
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
                  placeholder={formData.provider === 'ollama' ? 'http://localhost:11434' : formData.provider === 'openai' ? 'https://api.openai.com/v1' : 'https://api.anthropic.com/v1'}
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

