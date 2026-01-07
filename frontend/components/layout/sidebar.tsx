'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  Bot, 
  LayoutDashboard, 
  Settings, 
  ArrowLeftRight,
  Brain,
  GitBranch,
  Activity,
  Settings2,
  BarChart3
} from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * 侧边栏导航项配置
 */
const navigation = [
  {
    name: 'Dashboard',
    href: '/',
    icon: LayoutDashboard,
  },
  {
    name: 'Bots',
    href: '/bots',
    icon: Bot,
  },
  {
    name: 'Trades',
    href: '/trades',
    icon: Activity,
  },
  {
    name: 'Comparison',
    href: '/comparison',
    icon: BarChart3,
  },
]

const settingsNavigation = [
  {
    name: 'Exchanges',
    href: '/settings/exchanges',
    icon: ArrowLeftRight,
  },
  {
    name: 'LLM Configs',
    href: '/settings/llm',
    icon: Brain,
  },
  {
    name: 'Workflows',
    href: '/settings/workflows',
    icon: GitBranch,
  },
  {
    name: 'System Configs',
    href: '/settings/system-configs',
    icon: Settings2,
  },
]

/**
 * 应用侧边栏组件
 */
export function Sidebar() {
  const pathname = usePathname()

  return (
    <div className="flex h-full w-64 flex-col bg-card border-r">
      {/* Logo */}
      <div className="flex h-16 items-center px-6 border-b">
        <Link href="/" className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
            <Bot className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="text-xl font-bold">LangTrader</span>
        </Link>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
          Main
        </div>
        {navigation.map((item) => {
          const isActive = pathname === item.href || 
            (item.href !== '/' && pathname.startsWith(item.href))
          
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          )
        })}

        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mt-6 mb-2">
          Settings
        </div>
        {settingsNavigation.map((item) => {
          const isActive = pathname === item.href
          
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t">
        <div className="text-xs text-muted-foreground">
          <p>LangTrader v0.2.1</p>
          <p className="mt-1">AI-Powered Trading</p>
        </div>
      </div>
    </div>
  )
}

