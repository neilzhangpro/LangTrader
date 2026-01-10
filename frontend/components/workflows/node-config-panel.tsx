'use client'

import { useState, useEffect } from 'react'
import { X, Settings, Trash2, Power, PowerOff, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Textarea } from '@/components/ui/textarea'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

interface NodeConfigPanelProps {
  node: {
    id: string
    data: Record<string, unknown>
  } | null
  onClose: () => void
  onUpdate: (nodeId: string, updates: Record<string, unknown>) => void
  onDelete: (nodeId: string) => void
}

/**
 * 节点配置面板
 * 显示选中节点的详细信息和配置选项
 */
export function NodeConfigPanel({ node, onClose, onUpdate, onDelete }: NodeConfigPanelProps) {
  const [displayName, setDisplayName] = useState('')
  const [configJson, setConfigJson] = useState('{}')
  const [configError, setConfigError] = useState<string | null>(null)

  // 当节点变化时更新显示名称和配置
  useEffect(() => {
    if (node?.data?.label) {
      setDisplayName(String(node.data.label))
    }
    
    // 加载节点配置
    const config = node?.data?.config as Record<string, unknown> | undefined
    if (config && Object.keys(config).length > 0) {
      try {
        setConfigJson(JSON.stringify(config, null, 2))
        setConfigError(null)
      } catch (e) {
        setConfigJson('{}')
        setConfigError('配置格式错误')
      }
    } else {
      setConfigJson('{}')
      setConfigError(null)
    }
  }, [node?.data?.label, node?.data?.config])

  if (!node) return null

  // 获取节点数据的辅助函数
  const nodeData = node.data || {}
  const getString = (key: string) => String(nodeData[key] || '')
  const getBool = (key: string) => Boolean(nodeData[key])
  const getColor = () => String(nodeData.color || '#64748b')

  const handleToggleEnabled = () => {
    onUpdate(node.id, { enabled: !getBool('enabled') })
  }

  const handleUpdateName = () => {
    if (displayName.trim() && displayName !== getString('label')) {
      onUpdate(node.id, { label: displayName.trim() })
    }
  }

  const handleDelete = () => {
    if (confirm(`确定删除节点 "${getString('label')}" 吗？`)) {
      onDelete(node.id)
      onClose()
    }
  }

  // 更新配置参数
  const handleConfigChange = (value: string) => {
    setConfigJson(value)
    setConfigError(null)
    
    // 验证JSON格式并更新配置
    try {
      const parsed = JSON.parse(value)
      // 如果是有效对象，直接使用解析后的值
      if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
        // 如果配置为空对象，设置为undefined，否则使用解析后的配置
        const configToSave = Object.keys(parsed).length > 0 ? parsed : undefined
        onUpdate(node.id, { config: configToSave })
      } else {
        setConfigError('配置必须是JSON对象')
      }
    } catch (e) {
      // JSON格式错误，但不阻止编辑，只是显示错误提示
      setConfigError('JSON格式错误，请检查语法')
    }
  }

  const isEnabled = getBool('enabled')

  return (
    <Sheet open={!!node} onOpenChange={() => onClose()}>
      <SheetContent className="w-[400px] sm:w-[540px] flex flex-col">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            节点配置
          </SheetTitle>
          <SheetDescription>
            配置 {getString('label')} 节点的参数
          </SheetDescription>
        </SheetHeader>

        {/* 添加 overflow-y-auto 让内容可滚动，确保删除按钮可见 */}
        <div className="mt-6 space-y-6 flex-1 overflow-y-auto pb-6">
          {/* 基本信息 */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium flex items-center gap-2">
              基本信息
              <div 
                className="w-3 h-3 rounded-full"
                style={{ background: getColor() }}
              />
            </h4>
            
            <div className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="displayName">显示名称</Label>
                <div className="flex gap-2">
                  <Input
                    id="displayName"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="节点显示名称"
                  />
                  <Button 
                    size="sm" 
                    onClick={handleUpdateName}
                    disabled={displayName === getString('label')}
                  >
                    更新
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-muted-foreground">插件名称</Label>
                  <div className="text-sm font-mono bg-muted px-2 py-1 rounded">
                    {getString('pluginName')}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label className="text-muted-foreground">执行顺序</Label>
                  <div className="text-sm font-mono bg-muted px-2 py-1 rounded">
                    #{getString('executionOrder')}
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-muted-foreground">类别</Label>
                <Badge 
                  variant="outline"
                  style={{ 
                    borderColor: getColor(),
                    color: getColor(),
                  }}
                >
                  {getString('category')}
                </Badge>
              </div>

              {getString('description') && (
                <div className="space-y-2">
                  <Label className="text-muted-foreground">描述</Label>
                  <p className="text-sm text-muted-foreground">
                    {getString('description')}
                  </p>
                </div>
              )}

              {/* 依赖标识 */}
              <div className="flex gap-2">
                {getBool('requiresLlm') && (
                  <Badge variant="secondary">需要 LLM</Badge>
                )}
                {getBool('requiresTrader') && (
                  <Badge variant="secondary">需要 Trader</Badge>
                )}
              </div>
            </div>
          </div>

          <Separator />

          {/* 状态控制 */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium">状态控制</h4>
            
            <div className="flex items-center justify-between p-3 rounded-lg border">
              <div className="flex items-center gap-3">
                {isEnabled ? (
                  <Power className="h-5 w-5 text-green-500" />
                ) : (
                  <PowerOff className="h-5 w-5 text-muted-foreground" />
                )}
                <div>
                  <div className="text-sm font-medium">
                    {isEnabled ? '节点已启用' : '节点已禁用'}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {isEnabled 
                      ? '此节点将在工作流中执行' 
                      : '此节点将被跳过'
                    }
                  </div>
                </div>
              </div>
              <Switch
                checked={isEnabled}
                onCheckedChange={handleToggleEnabled}
              />
            </div>
          </div>

          <Separator />

          {/* 配置参数 */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium">配置参数</h4>
              {configError && (
                <div className="flex items-center gap-1 text-xs text-destructive">
                  <AlertCircle className="h-3 w-3" />
                  <span>{configError}</span>
                </div>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="config-json" className="text-xs text-muted-foreground">
                JSON 格式配置（适用于所有插件）
              </Label>
              <Textarea
                id="config-json"
                value={configJson}
                onChange={(e) => handleConfigChange(e.target.value)}
                placeholder='{"role_llm_ids": {"analyst": 1, "bull": 2}}'
                className="font-mono text-xs min-h-[200px]"
                spellCheck={false}
              />
              <p className="text-xs text-muted-foreground">
                示例：debate_decision 节点可配置 <code className="px-1 py-0.5 bg-muted rounded">role_llm_ids</code>
              </p>
            </div>
          </div>

          <Separator />

          {/* 危险操作 */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium text-destructive">危险操作</h4>
            <Button
              variant="destructive"
              className="w-full"
              onClick={handleDelete}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              删除此节点
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
