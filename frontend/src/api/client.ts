import type { Asset, Signal, Alert, Position, StreamChunk, ChatMessage, CardPayload, Monitor, AskAction } from './types'

const BASE = '/api/v1'

export async function fetchAssets(): Promise<Asset[]> {
  const res = await fetch(`${BASE}/assets`)
  if (!res.ok) throw new Error('Failed to fetch assets')
  return res.json()
}

export async function fetchAsset(symbol: string): Promise<Asset> {
  const res = await fetch(`${BASE}/assets/${symbol}`)
  if (!res.ok) throw new Error(`Failed to fetch ${symbol}`)
  return res.json()
}

export async function fetchIndicators(symbol: string) {
  const res = await fetch(`${BASE}/assets/${symbol}/indicators`)
  if (!res.ok) throw new Error(`Failed to fetch indicators for ${symbol}`)
  return res.json()
}

export async function fetchSignals(): Promise<Signal[]> {
  const res = await fetch(`${BASE}/signals`)
  if (!res.ok) throw new Error('Failed to fetch signals')
  return res.json()
}

export async function fetchSignal(symbol: string): Promise<Signal> {
  const res = await fetch(`${BASE}/signals/${symbol}`)
  if (!res.ok) throw new Error(`Failed to fetch signal for ${symbol}`)
  return res.json()
}

export async function fetchAlerts(): Promise<Alert[]> {
  const res = await fetch(`${BASE}/alerts`)
  if (!res.ok) throw new Error('Failed to fetch alerts')
  return res.json()
}

export async function fetchPositions(): Promise<Position[]> {
  const res = await fetch(`${BASE}/positions`)
  if (!res.ok) throw new Error('Failed to fetch positions')
  return res.json()
}

export async function fetchMonitors(): Promise<Monitor[]> {
  const res = await fetch(`${BASE}/monitors`)
  if (!res.ok) throw new Error('Failed to fetch monitors')
  return res.json()
}

export async function refreshMonitor(monitorId: string): Promise<Monitor> {
  const res = await fetch(`${BASE}/monitors/${monitorId}/refresh`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to refresh monitor')
  return res.json()
}

interface RawHistoryMessage {
  role: 'user' | 'assistant'
  content: string
  metadata: { cards?: CardPayload[] } | null
  timestamp: string
}

export async function fetchChatHistory(conversationId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${BASE}/chat/history/${conversationId}`)
  if (!res.ok) throw new Error('Failed to fetch chat history')
  const raw: RawHistoryMessage[] = await res.json()
  return raw.map((m, i) => ({
    id: `hist-${i}`,
    role: m.role,
    content: m.content,
    cards: m.metadata?.cards ?? [],
    toolCalls: [],
  }))
}

export async function* streamChat(
  message: string,
  conversationId?: string,
  action?: AskAction | null
): AsyncGenerator<StreamChunk> {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, conversation_id: conversationId, action: action ?? null }),
  })
  if (!res.ok) throw new Error('Chat request failed')
  if (!res.body) return

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') return
        try {
          yield JSON.parse(data) as StreamChunk
        } catch {
          // skip malformed chunk
        }
      }
    }
  }
}
