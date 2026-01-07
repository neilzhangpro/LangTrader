'use client'

import { useEffect, useRef, useState, useCallback } from 'react'

/**
 * WebSocket Hook
 * 
 * 安全说明：
 * - API Key 不再通过 URL 传递，改为连接后发送认证消息
 * - 这避免了 API Key 出现在浏览器历史记录和服务器日志中
 */

// WebSocket 消息类型
export interface WSMessage {
  event: string
  channel?: string
  data: Record<string, unknown>
  timestamp?: string
}

// WebSocket 命令
export interface WSCommand {
  action: 'auth' | 'subscribe' | 'unsubscribe' | 'ping'
  channel?: string
  api_key?: string
}

// WebSocket 事件类型
export type WSEventType = 
  | 'connected'
  | 'status'
  | 'trades'
  | 'decisions'
  | 'cycles'
  | 'subscribed'
  | 'unsubscribed'
  | 'error'
  | 'pong'

// 连接状态
export type ConnectionState = 'connecting' | 'authenticating' | 'connected' | 'disconnected' | 'error'

// API Key（从环境变量读取）
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || 'dev-key-123'
const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

/**
 * WebSocket Hook 配置
 */
interface UseWebSocketOptions {
  botId?: number
  onMessage?: (message: WSMessage) => void
  onStatusChange?: (status: Record<string, unknown>) => void
  onTrade?: (trade: Record<string, unknown>) => void
  onDecision?: (decision: Record<string, unknown>) => void
  onCycle?: (cycle: Record<string, unknown>) => void
  reconnectInterval?: number
  maxRetries?: number
}

/**
 * WebSocket Hook
 * 用于连接到 Bot 的实时更新
 */
export function useWebSocket({
  botId,
  onMessage,
  onStatusChange,
  onTrade,
  onDecision,
  onCycle,
  reconnectInterval = 5000,
  maxRetries = 10,
}: UseWebSocketOptions = {}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const isAuthenticatedRef = useRef(false)

  /**
   * 连接 WebSocket
   */
  const connect = useCallback(() => {
    if (!botId) return

    // 清理现有连接
    if (wsRef.current) {
      wsRef.current.close()
    }

    setConnectionState('connecting')
    isAuthenticatedRef.current = false

    // 不再在 URL 中传递 API Key
    const url = `${WS_BASE_URL}/ws/trading/${botId}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionState('authenticating')
      console.log(`[WS] Connection opened, authenticating...`)
      
      // 连接后立即发送认证消息
      ws.send(JSON.stringify({
        action: 'auth',
        api_key: API_KEY
      }))
    }

    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)
        setLastMessage(message)
        
        // 处理认证响应
        if (message.event === 'connected') {
          isAuthenticatedRef.current = true
          setConnectionState('connected')
          retriesRef.current = 0
          console.log(`[WS] Authenticated successfully for bot ${botId}`)
          
          // 检查是否有弃用警告
          if (message.data?.warning) {
            console.warn(`[WS] ${message.data.warning}`)
          }
          return
        }
        
        // 处理认证错误
        if (message.event === 'error' && !isAuthenticatedRef.current) {
          console.error(`[WS] Authentication failed: ${message.data?.message}`)
          setConnectionState('error')
          ws.close()
          return
        }
        
        // 调用通用回调
        onMessage?.(message)

        // 根据事件类型分发到特定回调
        const eventType = message.event?.toLowerCase()
        
        if (eventType === 'status' || message.channel?.includes(':status')) {
          onStatusChange?.(message.data)
        } else if (eventType === 'trade' || message.channel?.includes(':trades')) {
          onTrade?.(message.data)
        } else if (eventType === 'decision' || message.channel?.includes(':decisions')) {
          onDecision?.(message.data)
        } else if (eventType === 'cycle' || message.channel?.includes(':cycles')) {
          onCycle?.(message.data)
        }
      } catch (err) {
        console.error('[WS] Failed to parse message:', err)
      }
    }

    ws.onerror = (error) => {
      console.error('[WS] Error:', error)
      setConnectionState('error')
    }

    ws.onclose = (event) => {
      console.log(`[WS] Connection closed: ${event.code} ${event.reason}`)
      setConnectionState('disconnected')
      isAuthenticatedRef.current = false
      
      // 自动重连（除非是认证失败）
      if (event.code !== 4001 && retriesRef.current < maxRetries) {
        retriesRef.current += 1
        console.log(`[WS] Reconnecting in ${reconnectInterval}ms (attempt ${retriesRef.current}/${maxRetries})`)
        
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, reconnectInterval)
      } else if (event.code === 4001) {
        console.error('[WS] Authentication failed, not retrying')
        setConnectionState('error')
      } else {
        console.error('[WS] Max retries reached, giving up')
        setConnectionState('error')
      }
    }
  }, [botId, onMessage, onStatusChange, onTrade, onDecision, onCycle, reconnectInterval, maxRetries])

  /**
   * 断开连接
   */
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    
    isAuthenticatedRef.current = false
    setConnectionState('disconnected')
  }, [])

  /**
   * 发送命令
   */
  const sendCommand = useCallback((command: Omit<WSCommand, 'api_key'>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN && isAuthenticatedRef.current) {
      wsRef.current.send(JSON.stringify(command))
    }
  }, [])

  /**
   * 订阅频道
   */
  const subscribe = useCallback((channel: string) => {
    sendCommand({ action: 'subscribe', channel })
  }, [sendCommand])

  /**
   * 取消订阅
   */
  const unsubscribe = useCallback((channel: string) => {
    sendCommand({ action: 'unsubscribe', channel })
  }, [sendCommand])

  /**
   * 发送 ping
   */
  const ping = useCallback(() => {
    sendCommand({ action: 'ping' })
  }, [sendCommand])

  // 自动连接/断开
  useEffect(() => {
    if (botId) {
      connect()
    }
    
    return () => {
      disconnect()
    }
  }, [botId, connect, disconnect])

  // 心跳检测
  useEffect(() => {
    if (connectionState !== 'connected') return

    const interval = setInterval(() => {
      ping()
    }, 30000) // 每 30 秒 ping 一次

    return () => clearInterval(interval)
  }, [connectionState, ping])

  return {
    connectionState,
    lastMessage,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    ping,
    isConnected: connectionState === 'connected',
    isAuthenticated: isAuthenticatedRef.current,
  }
}

/**
 * 系统级 WebSocket Hook
 * 用于全局系统通知
 */
export function useSystemWebSocket({
  onAlert,
}: {
  onAlert?: (alert: Record<string, unknown>) => void
} = {}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const wsRef = useRef<WebSocket | null>(null)
  const isAuthenticatedRef = useRef(false)

  const connect = useCallback(() => {
    // 不再在 URL 中传递 API Key
    const url = `${WS_BASE_URL}/ws/system`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setConnectionState('authenticating')
      console.log('[WS System] Connection opened, authenticating...')
      
      // 发送认证消息
      ws.send(JSON.stringify({
        action: 'auth',
        api_key: API_KEY
      }))
    }

    ws.onmessage = (event) => {
      try {
        const message: WSMessage = JSON.parse(event.data)
        
        // 处理认证响应
        if (message.event === 'connected') {
          isAuthenticatedRef.current = true
          setConnectionState('connected')
          console.log('[WS System] Authenticated successfully')
          return
        }
        
        if (message.event === 'error' && !isAuthenticatedRef.current) {
          console.error(`[WS System] Authentication failed: ${message.data?.message}`)
          setConnectionState('error')
          ws.close()
          return
        }
        
        if (message.channel === 'system:alerts') {
          onAlert?.(message.data)
        }
      } catch (err) {
        console.error('[WS System] Failed to parse message:', err)
      }
    }

    ws.onerror = () => {
      setConnectionState('error')
    }

    ws.onclose = (event) => {
      setConnectionState('disconnected')
      isAuthenticatedRef.current = false
      
      // 自动重连（除非认证失败）
      if (event.code !== 4001) {
      setTimeout(connect, 5000)
      }
    }
  }, [onAlert])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    isAuthenticatedRef.current = false
    setConnectionState('disconnected')
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return {
    connectionState,
    isConnected: connectionState === 'connected',
  }
}
