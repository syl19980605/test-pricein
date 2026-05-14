import { useState, useCallback, useRef, useEffect } from 'react'
import { streamChat, fetchChatHistory } from '../api/client'
import type { ChatMessage, AskAction } from '../api/types'

let idCounter = 0
const nextId = () => `msg-${++idCounter}`

const STORAGE_KEY = 'bobby_conversation_id'

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const conversationId = useRef<string | undefined>(
    localStorage.getItem(STORAGE_KEY) || undefined
  )

  // 启动时若 localStorage 留有 conversationId，从后端恢复整段历史
  useEffect(() => {
    const cid = conversationId.current
    if (!cid) {
      setHistoryLoaded(true)
      return
    }
    fetchChatHistory(cid)
      .then(history => {
        if (history.length > 0) setMessages(history)
      })
      .catch(() => {
        // 历史拉取失败 → 当作新会话
        localStorage.removeItem(STORAGE_KEY)
        conversationId.current = undefined
      })
      .finally(() => setHistoryLoaded(true))
  }, [])

  const sendMessage = useCallback(async (text: string, action?: AskAction | null) => {
    if (!text.trim() || isStreaming) return

    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: text,
      cards: [],
      toolCalls: [],
    }
    const assistantId = nextId()
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      cards: [],
      toolCalls: [],
      streaming: true,
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setIsStreaming(true)

    const patch = (fn: (m: ChatMessage) => ChatMessage) => {
      setMessages(prev => prev.map(m => (m.id === assistantId ? fn(m) : m)))
    }

    try {
      for await (const chunk of streamChat(text, conversationId.current, action)) {
        if (chunk.type === 'conversation_id') {
          conversationId.current = chunk.conversation_id
          localStorage.setItem(STORAGE_KEY, chunk.conversation_id)
        } else if (chunk.type === 'text') {
          patch(m => ({ ...m, content: m.content + chunk.content }))
        } else if (chunk.type === 'tool_call') {
          patch(m => ({ ...m, toolCalls: [...m.toolCalls, { tool: chunk.tool, args: chunk.args }] }))
        } else if (chunk.type === 'card') {
          patch(m => ({ ...m, cards: [...m.cards, chunk.card] }))
        } else if (chunk.type === 'error') {
          patch(m => ({ ...m, content: m.content + `\n\n⚠️ 出错了：${chunk.message}` }))
        }
      }
    } catch (e) {
      patch(m => ({
        ...m,
        content: m.content + `\n\n⚠️ 连接失败：${e instanceof Error ? e.message : '未知错误'}`,
      }))
    } finally {
      patch(m => ({ ...m, streaming: false }))
      setIsStreaming(false)
    }
  }, [isStreaming])

  const clearHistory = useCallback(() => {
    if (isStreaming) return
    localStorage.removeItem(STORAGE_KEY)
    conversationId.current = undefined
    setMessages([])
  }, [isStreaming])

  return { messages, isStreaming, historyLoaded, sendMessage, clearHistory }
}
