import { useCallback, useEffect, useState } from 'react'
import type { ClientMessage, ServerMessage } from './types'

export type SocketStatus = 'connecting' | 'open' | 'closed'

export type MessageHandler = (message: ServerMessage) => void

const SERVER_TYPES: ReadonlySet<string> = new Set([
  'state',
  'devices',
  'campaigns',
  'frame',
  'notice',
  'card',
  'sprite',
  'cost'
])

const BACKOFF_MS: readonly number[] = [500, 1000, 2000, 5000]
const SUBPROTOCOL = 'desktop'

function parseServerMessage(raw: unknown): ServerMessage | null {
  if (typeof raw !== 'string') return null
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null) return null
  const type = (value as { type?: unknown }).type
  if (typeof type !== 'string' || !SERVER_TYPES.has(type)) return null
  return value as ServerMessage
}

export class GameSocket {
  private socket: WebSocket | null = null
  private handlers = new Set<MessageHandler>()
  private statusListeners = new Set<(status: SocketStatus) => void>()
  private timer: ReturnType<typeof setTimeout> | null = null
  private attempt = 0
  private running = false
  private current: SocketStatus = 'connecting'

  get status(): SocketStatus {
    return this.current
  }

  start(): void {
    if (this.running) return
    this.running = true
    this.attempt = 0
    void this.connect()
  }

  stop(): void {
    this.running = false
    if (this.timer !== null) clearTimeout(this.timer)
    this.timer = null
    const socket = this.socket
    this.socket = null
    if (socket) {
      socket.onopen = null
      socket.onmessage = null
      socket.onclose = null
      socket.onerror = null
      socket.close()
    }
    this.setStatus('closed')
  }

  send(message: ClientMessage): boolean {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message))
      return true
    }
    return false
  }

  subscribe(handler: MessageHandler): () => void {
    this.handlers.add(handler)
    return () => {
      this.handlers.delete(handler)
    }
  }

  onStatus(listener: (status: SocketStatus) => void): () => void {
    this.statusListeners.add(listener)
    return () => {
      this.statusListeners.delete(listener)
    }
  }

  private setStatus(status: SocketStatus): void {
    if (this.current === status) return
    this.current = status
    this.statusListeners.forEach((listener) => listener(status))
  }

  private async connect(): Promise<void> {
    if (!this.running) return
    this.setStatus('connecting')
    try {
      const { port, token } = await window.desktop.getConfig()
      if (!this.running) return
      const socket = new WebSocket(`ws://127.0.0.1:${port}/ws`, [SUBPROTOCOL, token])
      this.socket = socket
      socket.onopen = (): void => {
        this.attempt = 0
        this.setStatus('open')
      }
      socket.onmessage = (event: MessageEvent): void => {
        const message = parseServerMessage(event.data)
        if (message) this.handlers.forEach((handler) => handler(message))
      }
      socket.onclose = (): void => {
        if (this.socket !== socket) return
        this.socket = null
        this.setStatus('closed')
        this.scheduleReconnect()
      }
      socket.onerror = (): void => {
        socket.close()
      }
    } catch {
      this.setStatus('closed')
      this.scheduleReconnect()
    }
  }

  private scheduleReconnect(): void {
    if (!this.running || this.timer !== null) return
    const delay = BACKOFF_MS[Math.min(this.attempt, BACKOFF_MS.length - 1)]
    this.attempt += 1
    this.timer = setTimeout(() => {
      this.timer = null
      void this.connect()
    }, delay)
  }
}

export type GameConnection = Readonly<{
  status: SocketStatus
  send: (message: ClientMessage) => boolean
  subscribe: (handler: MessageHandler) => () => void
}>

export function useGameSocket(): GameConnection {
  const [socket] = useState(() => new GameSocket())
  const [status, setStatus] = useState<SocketStatus>('connecting')

  useEffect(() => {
    const off = socket.onStatus(setStatus)
    socket.start()
    return () => {
      off()
      socket.stop()
    }
  }, [socket])

  const send = useCallback((message: ClientMessage) => socket.send(message), [socket])
  const subscribe = useCallback((handler: MessageHandler) => socket.subscribe(handler), [socket])

  return { status, send, subscribe }
}
