import { useState } from 'react'
import { Send } from 'lucide-react'
import clsx from 'clsx'

interface ChatInputProps {
  onSend: (text: string) => void
  disabled: boolean
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')

  const handleSend = () => {
    if (!value.trim() || disabled) return
    onSend(value)
    setValue('')
  }

  return (
    <div className="border-t border-border bg-surface-light p-4">
      <div className="flex gap-2 items-end max-w-3xl mx-auto">
        <textarea
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          placeholder="问 Bobby：NVDA 现在值得买吗？/ 黄金的降息利好定价了吗？"
          rows={1}
          className="flex-1 bg-surface border border-border rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-primary/50 max-h-32"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className={clsx(
            'p-3 rounded-xl transition-all cursor-pointer',
            disabled || !value.trim()
              ? 'bg-surface-lighter text-text-secondary'
              : 'bg-primary text-white hover:bg-primary-dark'
          )}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
