'use client'

import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts'
import type { DailyPerformance } from '@/types/api'

interface PnLChartProps {
  data: DailyPerformance[]
  height?: number
}

/**
 * PnL 折线图组件
 */
export function PnLChart({ data, height = 300 }: PnLChartProps) {
  // 计算累计 PnL
  let cumulative = 0
  const chartData = data.map((item) => {
    cumulative += item.pnl_usd
    return {
      date: new Date(item.date).toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
      }),
      pnl: item.pnl_usd,
      cumulative: cumulative,
    }
  })

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis 
          dataKey="date" 
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
        />
        <YAxis 
          stroke="hsl(var(--muted-foreground))"
          fontSize={12}
          tickFormatter={(value) => `$${value.toFixed(0)}`}
        />
        <Tooltip 
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '8px',
          }}
          labelStyle={{ color: 'hsl(var(--foreground))' }}
          formatter={(value: number, name: string) => [
            `$${value.toFixed(2)}`,
            name === 'cumulative' ? 'Total PnL' : 'Daily PnL'
          ]}
        />
        <Line 
          type="monotone" 
          dataKey="cumulative" 
          stroke="hsl(var(--primary))" 
          strokeWidth={2}
          dot={false}
        />
        <Line 
          type="monotone" 
          dataKey="pnl" 
          stroke="hsl(var(--accent))" 
          strokeWidth={1}
          strokeDasharray="5 5"
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

