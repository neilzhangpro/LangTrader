import { create } from 'zustand'
import type { BotStatus, TradeRecord } from '@/types/api'

/**
 * Bot 状态 Store
 * 用于存储实时 Bot 状态和交易通知
 */
interface BotState {
  // Bot 状态缓存
  botStatuses: Record<number, BotStatus>
  
  // 最近的交易通知
  recentTrades: TradeRecord[]
  
  // 系统告警
  alerts: string[]
  
  // Actions
  updateBotStatus: (botId: number, status: BotStatus) => void
  addTrade: (trade: TradeRecord) => void
  addAlert: (alert: string) => void
  clearAlerts: () => void
}

export const useBotStore = create<BotState>((set) => ({
  botStatuses: {},
  recentTrades: [],
  alerts: [],

  updateBotStatus: (botId, status) =>
    set((state) => ({
      botStatuses: {
        ...state.botStatuses,
        [botId]: status,
      },
    })),

  addTrade: (trade) =>
    set((state) => ({
      recentTrades: [trade, ...state.recentTrades].slice(0, 100), // 保留最近 100 条
    })),

  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 50), // 保留最近 50 条
    })),

  clearAlerts: () =>
    set(() => ({
      alerts: [],
    })),
}))

