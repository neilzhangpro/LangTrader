'use client'

import { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Loader2, Pencil } from 'lucide-react'
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
import { toast } from '@/components/ui/use-toast'
import * as systemConfigsApi from '@/lib/api/system-configs'
import type { SystemConfig, SystemConfigCreate, SystemConfigUpdate } from '@/lib/api/system-configs'

// 配置值类型
const VALUE_TYPES = [
  { value: 'string', label: '字符串' },
  { value: 'integer', label: '整数' },
  { value: 'float', label: '浮点数' },
  { value: 'boolean', label: '布尔值' },
  { value: 'json', label: 'JSON' },
]

// 配置类别
const CATEGORIES = [
  { value: 'cache', label: '缓存配置' },
  { value: 'trading', label: '交易配置' },
  { value: 'api', label: 'API 配置' },
  { value: 'system', label: '系统配置' },
]

interface ConfigDialogProps {
  config?: SystemConfig // 编辑模式时传入
  children?: React.ReactNode
  onSuccess?: () => void
}

/**
 * 创建/编辑系统配置的 Dialog 组件
 */
export function ConfigDialog({ config, children, onSuccess }: ConfigDialogProps) {
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const isEditMode = !!config

  // 表单状态
  const [formData, setFormData] = useState<SystemConfigCreate>({
    config_key: '',
    config_value: '',
    value_type: 'string',
    category: 'system',
    description: '',
    is_editable: true,
  })

  // 编辑模式时填充数据
  useEffect(() => {
    if (config && open) {
      setFormData({
        config_key: config.config_key,
        config_value: config.config_value,
        value_type: config.value_type as SystemConfigCreate['value_type'],
        category: config.category || 'system',
        description: config.description || '',
        is_editable: config.is_editable,
      })
    }
  }, [config, open])

  // 创建 mutation
  const createMutation = useMutation({
    mutationFn: systemConfigsApi.createSystemConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-configs'] })
      toast({
        title: '配置创建成功',
        description: `成功创建配置 "${formData.config_key}"`,
      })
      setOpen(false)
      resetForm()
      onSuccess?.()
    },
    onError: (error: Error) => {
      toast({
        title: '创建失败',
        description: error.message || '创建配置时发生错误',
        variant: 'destructive',
      })
    },
  })

  // 更新 mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: SystemConfigUpdate }) =>
      systemConfigsApi.updateSystemConfig(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-configs'] })
      toast({
        title: '配置更新成功',
        description: `成功更新配置 "${formData.config_key}"`,
      })
      setOpen(false)
      onSuccess?.()
    },
    onError: (error: Error) => {
      toast({
        title: '更新失败',
        description: error.message || '更新配置时发生错误',
        variant: 'destructive',
      })
    },
  })

  // 重置表单
  const resetForm = () => {
    setFormData({
      config_key: '',
      config_value: '',
      value_type: 'string',
      category: 'system',
      description: '',
      is_editable: true,
    })
  }

  // 验证配置值格式
  const validateValue = (): boolean => {
    const { config_value, value_type } = formData
    
    try {
      switch (value_type) {
        case 'integer':
          if (!/^-?\d+$/.test(config_value)) {
            toast({
              title: '格式错误',
              description: '整数格式不正确',
              variant: 'destructive',
            })
            return false
          }
          break
        case 'float':
          if (isNaN(parseFloat(config_value))) {
            toast({
              title: '格式错误',
              description: '浮点数格式不正确',
              variant: 'destructive',
            })
            return false
          }
          break
        case 'boolean':
          if (!['true', 'false', '1', '0', 'yes', 'no'].includes(config_value.toLowerCase())) {
            toast({
              title: '格式错误',
              description: '布尔值应为 true/false',
              variant: 'destructive',
            })
            return false
          }
          break
        case 'json':
          JSON.parse(config_value)
          break
      }
      return true
    } catch {
      toast({
        title: '格式错误',
        description: 'JSON 格式不正确',
        variant: 'destructive',
      })
      return false
    }
  }

  // 提交表单
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.config_key || !formData.config_value) {
      toast({
        title: '验证错误',
        description: '请填写必填字段',
        variant: 'destructive',
      })
      return
    }

    if (!validateValue()) {
      return
    }

    if (isEditMode && config) {
      updateMutation.mutate({
        id: config.id,
        data: {
          config_value: formData.config_value,
          value_type: formData.value_type,
          category: formData.category,
          description: formData.description,
          is_editable: formData.is_editable,
        },
      })
    } else {
      createMutation.mutate(formData)
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children || (
          <Button>
            {isEditMode ? (
              <>
                <Pencil className="h-4 w-4 mr-2" />
                编辑
              </>
            ) : (
              <>
                <Plus className="h-4 w-4 mr-2" />
                添加配置
              </>
            )}
          </Button>
        )}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[550px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{isEditMode ? '编辑配置' : '添加配置'}</DialogTitle>
            <DialogDescription>
              {isEditMode ? '修改系统配置参数' : '添加新的系统配置参数'}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            {/* 配置键 */}
            <div className="grid gap-2">
              <Label htmlFor="config_key">配置键 *</Label>
              <Input
                id="config_key"
                placeholder="cache.ttl.tickers"
                value={formData.config_key}
                onChange={(e) => setFormData({ ...formData, config_key: e.target.value })}
                disabled={isEditMode}
              />
              <p className="text-xs text-muted-foreground">
                使用点分隔命名空间，如 cache.ttl.tickers
              </p>
            </div>

            {/* 类别 */}
            <div className="grid gap-2">
              <Label htmlFor="category">类别</Label>
              <Select
                value={formData.category}
                onValueChange={(value) => setFormData({ ...formData, category: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择类别" />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((cat) => (
                    <SelectItem key={cat.value} value={cat.value}>
                      {cat.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 值类型 */}
            <div className="grid gap-2">
              <Label htmlFor="value_type">值类型</Label>
              <Select
                value={formData.value_type}
                onValueChange={(value) => setFormData({ 
                  ...formData, 
                  value_type: value as SystemConfigCreate['value_type'] 
                })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="选择类型" />
                </SelectTrigger>
                <SelectContent>
                  {VALUE_TYPES.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 配置值 */}
            <div className="grid gap-2">
              <Label htmlFor="config_value">配置值 *</Label>
              {formData.value_type === 'json' ? (
                <Textarea
                  id="config_value"
                  placeholder='{"key": "value"}'
                  value={formData.config_value}
                  onChange={(e) => setFormData({ ...formData, config_value: e.target.value })}
                  rows={4}
                  className="font-mono text-sm"
                />
              ) : formData.value_type === 'boolean' ? (
                <Select
                  value={formData.config_value || 'false'}
                  onValueChange={(value) => setFormData({ ...formData, config_value: value })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="true">true</SelectItem>
                    <SelectItem value="false">false</SelectItem>
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  id="config_value"
                  type={formData.value_type === 'integer' || formData.value_type === 'float' ? 'number' : 'text'}
                  step={formData.value_type === 'float' ? '0.01' : '1'}
                  placeholder={formData.value_type === 'integer' ? '60' : '配置值'}
                  value={formData.config_value}
                  onChange={(e) => setFormData({ ...formData, config_value: e.target.value })}
                />
              )}
            </div>

            {/* 描述 */}
            <div className="grid gap-2">
              <Label htmlFor="description">描述</Label>
              <Textarea
                id="description"
                placeholder="配置项的用途说明"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={2}
              />
            </div>

            {/* 可编辑开关 */}
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="is_editable">允许编辑</Label>
                <p className="text-xs text-muted-foreground">
                  禁用后将无法通过界面修改
                </p>
              </div>
              <Switch
                id="is_editable"
                checked={formData.is_editable}
                onCheckedChange={(checked) => setFormData({ ...formData, is_editable: checked })}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>
              取消
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {isEditMode ? '保存' : '创建'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

