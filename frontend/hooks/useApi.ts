'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as botsApi from '@/lib/api/bots'
import * as exchangesApi from '@/lib/api/exchanges'
import * as llmConfigsApi from '@/lib/api/llm-configs'
import * as workflowsApi from '@/lib/api/workflows'
import * as performanceApi from '@/lib/api/performance'
import * as tradesApi from '@/lib/api/trades'

// =============================================================================
// Bot Hooks
// =============================================================================

/**
 * 获取 Bot 列表
 */
export function useBots(params?: Parameters<typeof botsApi.listBots>[0]) {
  return useQuery({
    queryKey: ['bots', params],
    queryFn: () => botsApi.listBots(params),
  })
}

/**
 * 获取单个 Bot
 */
export function useBot(botId: number) {
  return useQuery({
    queryKey: ['bot', botId],
    queryFn: () => botsApi.getBot(botId),
    enabled: !!botId,
  })
}

/**
 * 获取 Bot 状态
 */
export function useBotStatus(botId: number, options?: { refetchInterval?: number }) {
  return useQuery({
    queryKey: ['bot-status', botId],
    queryFn: () => botsApi.getBotStatus(botId),
    enabled: !!botId,
    refetchInterval: options?.refetchInterval ?? 5000,
  })
}

/**
 * Bot 控制 Mutations
 */
export function useBotControl() {
  const queryClient = useQueryClient()

  const start = useMutation({
    mutationFn: botsApi.startBot,
    onSuccess: (_, botId) => {
      queryClient.invalidateQueries({ queryKey: ['bot-status', botId] })
    },
  })

  const stop = useMutation({
    mutationFn: botsApi.stopBot,
    onSuccess: (_, botId) => {
      queryClient.invalidateQueries({ queryKey: ['bot-status', botId] })
    },
  })

  const restart = useMutation({
    mutationFn: botsApi.restartBot,
    onSuccess: (_, botId) => {
      queryClient.invalidateQueries({ queryKey: ['bot-status', botId] })
    },
  })

  return { start, stop, restart }
}

// =============================================================================
// Exchange Hooks
// =============================================================================

/**
 * 获取交易所列表
 */
export function useExchanges() {
  return useQuery({
    queryKey: ['exchanges'],
    queryFn: exchangesApi.listExchanges,
  })
}

/**
 * 测试交易所连接
 */
export function useTestExchange() {
  return useMutation({
    mutationFn: exchangesApi.testExchange,
  })
}

// =============================================================================
// LLM Config Hooks
// =============================================================================

/**
 * 获取 LLM 配置列表
 */
export function useLLMConfigs(enabledOnly?: boolean) {
  return useQuery({
    queryKey: ['llm-configs', enabledOnly],
    queryFn: () => llmConfigsApi.listLLMConfigs(enabledOnly),
  })
}

/**
 * 设置默认 LLM
 */
export function useSetDefaultLLM() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: llmConfigsApi.setDefaultLLMConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llm-configs'] })
    },
  })
}

// =============================================================================
// Workflow Hooks
// =============================================================================

/**
 * 获取工作流列表
 */
export function useWorkflows() {
  return useQuery({
    queryKey: ['workflows'],
    queryFn: workflowsApi.listWorkflows,
  })
}

/**
 * 获取插件列表
 */
export function usePlugins() {
  return useQuery({
    queryKey: ['plugins'],
    queryFn: workflowsApi.listPlugins,
  })
}

// =============================================================================
// Performance Hooks
// =============================================================================

/**
 * 获取 Bot 绩效指标
 */
export function usePerformance(botId: number, window?: number) {
  return useQuery({
    queryKey: ['performance', botId, window],
    queryFn: () => performanceApi.getBotPerformance(botId, window),
    enabled: !!botId,
  })
}

// =============================================================================
// Trade Hooks
// =============================================================================

/**
 * 获取交易列表
 */
export function useTrades(params?: Parameters<typeof tradesApi.listTrades>[0]) {
  return useQuery({
    queryKey: ['trades', params],
    queryFn: () => tradesApi.listTrades(params),
  })
}

/**
 * 获取每日绩效
 */
export function useDailyPerformance(botId: number, days?: number) {
  return useQuery({
    queryKey: ['daily-performance', botId, days],
    queryFn: () => tradesApi.getDailyPerformance(botId, days),
    enabled: !!botId,
  })
}

