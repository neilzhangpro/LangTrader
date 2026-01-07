'use client'

import { Bell, Settings, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

/**
 * 页面顶部导航栏
 */
export function Header() {
  const queryClient = useQueryClient()
  const [isRefreshing, setIsRefreshing] = useState(false)

  /**
   * 刷新所有数据
   */
  const handleRefresh = async () => {
    setIsRefreshing(true)
    await queryClient.invalidateQueries()
    setTimeout(() => setIsRefreshing(false), 500)
  }

  return (
    <header className="h-16 border-b bg-card flex items-center justify-between px-6">
      {/* Left side - Breadcrumb or title could go here */}
      <div>
        {/* Reserved for breadcrumb */}
      </div>

      {/* Right side - Actions */}
      <div className="flex items-center gap-2">
        {/* Refresh Button */}
        <Button 
          variant="ghost" 
          size="icon"
          onClick={handleRefresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={`h-5 w-5 ${isRefreshing ? 'animate-spin' : ''}`} />
        </Button>

        {/* Notifications */}
        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
        </Button>

        {/* Settings */}
        <Button variant="ghost" size="icon">
          <Settings className="h-5 w-5" />
        </Button>
      </div>
    </header>
  )
}

