'use client'

import { useQuery } from '@tanstack/react-query'
import { Bot, Plus, Search, Filter } from 'lucide-react'
import { useState } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { BotCard } from '@/components/bots/bot-card'
import { CreateBotDialog } from '@/components/bots/create-bot-dialog'
import * as botsApi from '@/lib/api/bots'

/**
 * Bot 列表页面
 * 展示所有 Bot 并提供管理功能
 */
export default function BotsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [filterMode, setFilterMode] = useState<string | null>(null)

  // 获取 Bot 列表
  const { data: botsData, isLoading } = useQuery({
    queryKey: ['bots'],
    queryFn: () => botsApi.listBots({ page: 1, page_size: 100 }),
  })

  const bots = botsData?.items || []

  // 过滤 Bots
  const filteredBots = bots.filter((bot) => {
    const matchesSearch = !searchQuery || 
      bot.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      bot.display_name?.toLowerCase().includes(searchQuery.toLowerCase())
    
    const matchesMode = !filterMode || bot.trading_mode === filterMode

    return matchesSearch && matchesMode
  })

  // 统计信息
  const activeBots = bots.filter(b => b.is_active).length
  const liveBots = bots.filter(b => b.trading_mode === 'live').length
  const paperBots = bots.filter(b => b.trading_mode === 'paper').length

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Trading Bots</h1>
          <p className="text-muted-foreground">
            Manage your trading bots and monitor their status
          </p>
        </div>
        <CreateBotDialog />
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Total Bots</p>
          <p className="text-2xl font-bold">{bots.length}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Active</p>
          <p className="text-2xl font-bold text-green-500">{activeBots}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Live Trading</p>
          <p className="text-2xl font-bold text-yellow-500">{liveBots}</p>
        </Card>
        <Card className="p-4">
          <p className="text-sm text-muted-foreground">Paper Trading</p>
          <p className="text-2xl font-bold text-blue-500">{paperBots}</p>
        </Card>
      </div>

      {/* 搜索和过滤 */}
      <div className="flex gap-4">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search bots..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-2">
          <Button
            variant={filterMode === null ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterMode(null)}
          >
            All
          </Button>
          <Button
            variant={filterMode === 'live' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterMode('live')}
          >
            Live
          </Button>
          <Button
            variant={filterMode === 'paper' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilterMode('paper')}
          >
            Paper
          </Button>
        </div>
      </div>

      {/* Bot 网格 */}
      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Card key={i} className="h-64 animate-pulse bg-muted" />
          ))}
        </div>
      ) : filteredBots.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredBots.map((bot) => (
            <BotCard key={bot.id} bot={bot} />
          ))}
        </div>
      ) : bots.length === 0 ? (
        <Card className="p-12 text-center">
          <Bot className="h-16 w-16 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-xl font-medium mb-2">No Bots Yet</h3>
          <p className="text-muted-foreground mb-4">
            Create your first trading bot to start automated trading
          </p>
          <CreateBotDialog>
            <Button>
              <Plus className="h-4 w-4 mr-2" />
              Create Your First Bot
            </Button>
          </CreateBotDialog>
        </Card>
      ) : (
        <Card className="p-8 text-center">
          <Filter className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-lg font-medium mb-2">No Results</h3>
          <p className="text-muted-foreground">
            No bots match your search criteria
          </p>
        </Card>
      )}
    </div>
  )
}

