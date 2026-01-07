'use client'

import { formatCurrency, formatDateTime, cn, getPnLColorClass } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import type { TradeRecord } from '@/types/api'

interface TradesTableProps {
  trades: TradeRecord[]
  isLoading?: boolean
}

/**
 * 交易历史表格组件
 */
export function TradesTable({ trades, isLoading }: TradesTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-12 bg-muted animate-pulse rounded" />
        ))}
      </div>
    )
  }

  if (trades.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No trades found
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
            <th className="text-left py-3 px-2 font-medium">Action</th>
            <th className="text-right py-3 px-2 font-medium">Entry</th>
            <th className="text-right py-3 px-2 font-medium">Exit</th>
            <th className="text-right py-3 px-2 font-medium">Amount</th>
            <th className="text-right py-3 px-2 font-medium">PnL</th>
            <th className="text-left py-3 px-2 font-medium">Status</th>
            <th className="text-left py-3 px-2 font-medium">Time</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((trade) => (
            <tr 
              key={trade.id} 
              className="border-b hover:bg-muted/50 transition-colors"
            >
              <td className="py-3 px-2 font-mono font-medium">
                {trade.symbol}
              </td>
              <td className="py-3 px-2">
                <Badge variant={trade.side === 'long' ? 'success' : 'error'}>
                  {trade.side.toUpperCase()}
                </Badge>
              </td>
              <td className="py-3 px-2 text-muted-foreground">
                {trade.action}
              </td>
              <td className="py-3 px-2 text-right font-mono">
                {trade.entry_price != null 
                  ? formatCurrency(Number(trade.entry_price), 4)
                  : '-'
                }
              </td>
              <td className="py-3 px-2 text-right font-mono">
                {trade.exit_price != null 
                  ? formatCurrency(Number(trade.exit_price), 4)
                  : '-'
                }
              </td>
              <td className="py-3 px-2 text-right font-mono">
                {Number(trade.amount).toFixed(6)}
              </td>
              <td className={cn(
                'py-3 px-2 text-right font-mono font-medium',
                trade.pnl_usd != null ? getPnLColorClass(Number(trade.pnl_usd)) : ''
              )}>
                {trade.pnl_usd != null 
                  ? formatCurrency(Number(trade.pnl_usd))
                  : '-'
                }
              </td>
              <td className="py-3 px-2">
                <Badge variant={trade.status === 'open' ? 'warning' : 'secondary'}>
                  {trade.status}
                </Badge>
              </td>
              <td className="py-3 px-2 text-muted-foreground">
                {formatDateTime(trade.opened_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

