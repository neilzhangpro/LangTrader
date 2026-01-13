'use client'

import { formatCurrency, cn, getPnLColorClass } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { PositionInfo } from '@/types/api'

interface PositionsTableProps {
  positions: PositionInfo[]
  isLoading?: boolean
}

/**
 * 持仓表格组件
 */
export function PositionsTable({ positions, isLoading }: PositionsTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 bg-muted animate-pulse rounded" />
        ))}
      </div>
    )
  }

  if (positions.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No open positions
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-muted-foreground">
            <th className="text-left py-3 px-2 font-medium">Symbol</th>
            <th className="text-left py-3 px-2 font-medium">Side</th>
            <th className="text-right py-3 px-2 font-medium">Size</th>
            <th className="text-right py-3 px-2 font-medium">Entry Price</th>
            <th className="text-right py-3 px-2 font-medium">Mark Price</th>
            <th className="text-right py-3 px-2 font-medium">Unrealized PnL</th>
            <th className="text-right py-3 px-2 font-medium">Leverage</th>
            <th className="text-right py-3 px-2 font-medium">Margin</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((position, index) => {
            // 计算 ROE（Return on Equity）= 价格变动百分比 × 杠杆
            // 这与交易所显示的盈亏百分比一致
            const effectiveMarkPrice = position.mark_price > 0 ? position.mark_price : position.entry_price
            const priceChangePct = position.entry_price > 0 && effectiveMarkPrice > 0
              ? ((effectiveMarkPrice - position.entry_price) / position.entry_price * 100)
                * (position.side === 'long' ? 1 : -1)
              : 0
            // ROE = 价格变动 × 杠杆
            const pnlPercent = priceChangePct * position.leverage

            return (
              <tr 
                key={`${position.symbol}-${index}`} 
                className="border-b hover:bg-muted/50 transition-colors"
              >
                <td className="py-3 px-2 font-mono font-medium">
                  {position.symbol}
                </td>
                <td className="py-3 px-2">
                  <Badge variant={position.side === 'long' ? 'success' : 'error'}>
                    {position.side.toUpperCase()}
                  </Badge>
                </td>
                <td className="py-3 px-2 text-right font-mono">
                  {position.size.toFixed(6)}
                </td>
                <td className="py-3 px-2 text-right font-mono">
                  {formatCurrency(position.entry_price, 4)}
                </td>
                <td className="py-3 px-2 text-right font-mono">
                  {formatCurrency(position.mark_price, 4)}
                </td>
                <td className={cn(
                  'py-3 px-2 text-right font-mono font-medium',
                  getPnLColorClass(position.unrealized_pnl)
                )}>
                  {formatCurrency(position.unrealized_pnl)}
                  <span className="text-xs ml-1">
                    ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
                  </span>
                </td>
                <td className="py-3 px-2 text-right font-mono">
                  {position.leverage}x
                </td>
                <td className="py-3 px-2 text-right font-mono">
                  {formatCurrency(position.margin_used)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

