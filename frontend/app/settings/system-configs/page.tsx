'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Settings2,
  Trash2,
  Search,
  Filter,
  RefreshCw,
  Copy,
  Check,
  Pencil,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { toast } from '@/components/ui/use-toast'
import { ConfigDialog } from '@/components/system-configs/config-dialog'
import * as systemConfigsApi from '@/lib/api/system-configs'
import type { SystemConfig } from '@/lib/api/system-configs'

// 类别颜色映射
const CATEGORY_COLORS: Record<string, string> = {
  cache: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
  trading: 'bg-green-500/20 text-green-500 border-green-500/30',
  api: 'bg-purple-500/20 text-purple-500 border-purple-500/30',
  system: 'bg-orange-500/20 text-orange-500 border-orange-500/30',
}

// 值类型颜色映射
const VALUE_TYPE_COLORS: Record<string, string> = {
  string: 'bg-gray-500/20 text-gray-400',
  integer: 'bg-cyan-500/20 text-cyan-400',
  float: 'bg-teal-500/20 text-teal-400',
  boolean: 'bg-amber-500/20 text-amber-400',
  json: 'bg-pink-500/20 text-pink-400',
}

/**
 * 系统配置管理页面
 */
export default function SystemConfigsPage() {
  const queryClient = useQueryClient()
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [copiedKey, setCopiedKey] = useState<string | null>(null)

  // 获取配置列表
  const { data: configs, isLoading, refetch } = useQuery({
    queryKey: ['system-configs'],
    queryFn: () => systemConfigsApi.listSystemConfigs(),
  })

  // 获取类别列表
  const { data: categories } = useQuery({
    queryKey: ['system-configs-categories'],
    queryFn: () => systemConfigsApi.listCategories(),
  })

  // 删除配置
  const deleteMutation = useMutation({
    mutationFn: systemConfigsApi.deleteSystemConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system-configs'] })
      queryClient.invalidateQueries({ queryKey: ['system-configs-categories'] })
      toast({
        title: '删除成功',
        description: '配置已删除',
      })
    },
    onError: (error: Error) => {
      toast({
        title: '删除失败',
        description: error.message || '删除配置时发生错误',
        variant: 'destructive',
      })
    },
  })

  // 复制配置键
  const handleCopyKey = async (key: string) => {
    await navigator.clipboard.writeText(key)
    setCopiedKey(key)
    setTimeout(() => setCopiedKey(null), 2000)
    toast({
      title: '已复制',
      description: `配置键 "${key}" 已复制到剪贴板`,
    })
  }

  // 过滤配置
  const filteredConfigs = configs?.filter((config) => {
    const matchesSearch =
      config.config_key.toLowerCase().includes(searchTerm.toLowerCase()) ||
      config.description?.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesCategory =
      selectedCategory === 'all' || config.category === selectedCategory
    return matchesSearch && matchesCategory
  })

  // 按类别分组统计
  const categoryStats = configs?.reduce((acc, config) => {
    const cat = config.category || 'uncategorized'
    acc[cat] = (acc[cat] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  // 格式化显示值
  const formatValue = (config: SystemConfig) => {
    const { config_value, value_type } = config
    if (value_type === 'json') {
      try {
        return JSON.stringify(JSON.parse(config_value), null, 2)
      } catch {
        return config_value
      }
    }
    if (value_type === 'boolean') {
      return config_value.toLowerCase() === 'true' ? '✓ true' : '✗ false'
    }
    return config_value
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Settings2 className="h-8 w-8" />
            系统配置
          </h1>
          <p className="text-muted-foreground">
            管理系统全局配置参数
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-2" />
            刷新
          </Button>
          <ConfigDialog />
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              总配置数
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{configs?.length || 0}</div>
          </CardContent>
        </Card>
        {Object.entries(categoryStats || {}).slice(0, 3).map(([cat, count]) => (
          <Card key={cat}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground capitalize">
                {cat}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{count}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* 筛选和搜索 */}
      <Card>
        <CardHeader>
          <CardTitle>配置列表</CardTitle>
          <CardDescription>
            点击配置键可复制，点击编辑按钮修改配置
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="搜索配置键或描述..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={selectedCategory} onValueChange={setSelectedCategory}>
              <SelectTrigger className="w-[180px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="筛选类别" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部类别</SelectItem>
                {categories?.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* 配置表格 */}
          {isLoading ? (
            <div className="h-48 flex items-center justify-center">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : filteredConfigs && filteredConfigs.length > 0 ? (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[300px]">配置键</TableHead>
                    <TableHead className="w-[100px]">类别</TableHead>
                    <TableHead className="w-[80px]">类型</TableHead>
                    <TableHead>配置值</TableHead>
                    <TableHead className="w-[200px]">描述</TableHead>
                    <TableHead className="w-[100px] text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredConfigs.map((config) => (
                    <TableRow key={config.id}>
                      <TableCell>
                        <button
                          onClick={() => handleCopyKey(config.config_key)}
                          className="flex items-center gap-2 font-mono text-sm hover:text-primary transition-colors group"
                        >
                          {config.config_key}
                          {copiedKey === config.config_key ? (
                            <Check className="h-3 w-3 text-green-500" />
                          ) : (
                            <Copy className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                          )}
                        </button>
                      </TableCell>
                      <TableCell>
                        {config.category && (
                          <Badge
                            variant="outline"
                            className={CATEGORY_COLORS[config.category] || ''}
                          >
                            {config.category}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="secondary"
                          className={VALUE_TYPE_COLORS[config.value_type] || ''}
                        >
                          {config.value_type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <code className="text-sm bg-muted px-2 py-1 rounded max-w-[300px] truncate block">
                          {formatValue(config)}
                        </code>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground truncate block max-w-[200px]">
                          {config.description || '-'}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <ConfigDialog config={config}>
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={!config.is_editable}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                          </ConfigDialog>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:text-destructive"
                                disabled={!config.is_editable}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>确认删除</AlertDialogTitle>
                                <AlertDialogDescription>
                                  确定要删除配置 &quot;{config.config_key}&quot; 吗？此操作无法撤销。
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>取消</AlertDialogCancel>
                                <AlertDialogAction
                                  onClick={() => deleteMutation.mutate(config.id)}
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                >
                                  删除
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="h-48 flex flex-col items-center justify-center text-muted-foreground">
              <Settings2 className="h-12 w-12 mb-4" />
              <p className="text-lg font-medium">暂无配置</p>
              <p className="text-sm">点击上方「添加配置」按钮创建第一个配置</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

