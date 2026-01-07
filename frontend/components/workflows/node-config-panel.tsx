'use client'

import { useState, useEffect } from 'react'
import { X, Settings, Trash2, Power, PowerOff } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
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

  // 当节点变化时更新显示名称
  useEffect(() => {
    if (node?.data?.label) {
      setDisplayName(String(node.data.label))
    }
  }, [node?.data?.label])

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

          {/* 配置参数（TODO：根据插件 schema 动态渲染） */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium">配置参数</h4>
            <div className="p-4 rounded-lg border border-dashed text-center text-sm text-muted-foreground">
              <Settings className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p>插件配置参数</p>
              <p className="text-xs mt-1">
                （后续版本将根据插件 Schema 动态渲染表单）
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
