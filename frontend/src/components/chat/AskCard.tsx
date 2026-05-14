import { useState } from 'react'
import { MessageCircleQuestion, Check } from 'lucide-react'
import clsx from 'clsx'
import type { AskBlock, AskAction } from '../../api/types'

interface AskCardProps {
  data: AskBlock
  onSend?: (text: string, action?: AskAction | null) => void
}

/** 交互式 Ask 组件：Bobby 在场景流程中向用户提问。
 * 选项带 action = 后端确定性执行该工具；不带 action = 走 MiMo 对话。 */
export default function AskCard({ data, onSend }: AskCardProps) {
  const [chosen, setChosen] = useState<string | null>(null)

  const handleClick = (label: string, message: string, action?: AskAction | null) => {
    if (chosen || !onSend) return
    setChosen(label)
    onSend(message, action)
  }

  return (
    <div className="mt-3 bg-primary/5 border border-primary/30 rounded-xl p-4 max-w-md">
      <div className="flex items-center gap-2 mb-3">
        <MessageCircleQuestion size={16} className="text-primary" />
        <span className="text-sm font-medium leading-snug">{data.question}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {data.options.map(opt => {
          const isChosen = chosen === opt.label
          const isDisabled = chosen !== null
          return (
            <button
              key={opt.label}
              onClick={() => handleClick(opt.label, opt.message, opt.action)}
              disabled={isDisabled}
              className={clsx(
                'flex items-center gap-1 text-xs font-medium px-3 py-1.5 rounded-lg transition-all cursor-pointer',
                isChosen && 'bg-primary text-white',
                !isChosen && isDisabled && 'bg-surface text-text-secondary opacity-40',
                !isDisabled && opt.variant === 'primary' && 'bg-primary text-white hover:bg-primary-dark',
                !isDisabled && opt.variant !== 'primary' &&
                  'bg-surface border border-border text-text-primary hover:border-primary/50',
              )}
            >
              {isChosen && <Check size={12} />}
              {opt.label}
            </button>
          )
        })}
      </div>
      {chosen && (
        <p className="text-[10px] text-text-secondary mt-2">已选择「{chosen}」，Bobby 正在处理…</p>
      )}
    </div>
  )
}
