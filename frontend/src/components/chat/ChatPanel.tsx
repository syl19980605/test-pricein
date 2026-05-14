import { useEffect, useRef } from 'react'
import { Plus } from 'lucide-react'
import type { ChatMessage, AskAction } from '../../api/types'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'

const SUGGESTIONS = [
  'NVDA 现在值得买吗？',
  '黄金最近的降息利好，是不是已经定价了？',
  '我看到英伟达获批向中国销售H200芯片，这个利好定价了吗？',
  '帮我做一个包含 BTC 和 NVDA 的稳健型组合',
]

interface ChatPanelProps {
  messages: ChatMessage[]
  isStreaming: boolean
  sendMessage: (text: string, action?: AskAction | null) => void
  onClearHistory: () => void
}

export default function ChatPanel({ messages, isStreaming, sendMessage, onClearHistory }: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* 会话状态条：展示「上下文保持中」+ 新对话入口 */}
      <div className="flex items-center justify-between px-6 py-2 border-b border-border bg-surface-light/50">
        <span className="text-xs text-text-secondary">
          {messages.length > 0
            ? `上下文保持中 · 共 ${messages.length} 条消息（刷新/切换页面不丢失）`
            : '新对话'}
        </span>
        <button
          onClick={onClearHistory}
          disabled={isStreaming || messages.length === 0}
          className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-40 transition-colors cursor-pointer"
        >
          <Plus size={12} />
          新对话
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 min-h-0">
        <div className="max-w-3xl mx-auto space-y-5">
          {messages.length === 0 && (
            <div className="text-center py-12">
              <div className="w-16 h-16 rounded-2xl bg-primary/20 text-primary flex items-center justify-center text-3xl font-bold mx-auto mb-4">
                B
              </div>
              <h2 className="text-xl font-bold mb-1">我是 Bobby</h2>
              <p className="text-text-secondary text-sm mb-6">
                你的头部资产智能监控助手 — 用数据说话，关注消息是否已被定价
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-xl mx-auto">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className="text-left text-sm bg-surface-light border border-border rounded-xl px-4 py-3 hover:border-primary/50 transition-colors cursor-pointer"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} onSend={sendMessage} />
          ))}
        </div>
      </div>
      <ChatInput onSend={sendMessage} disabled={isStreaming} />
    </div>
  )
}
