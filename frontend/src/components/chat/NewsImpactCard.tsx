import clsx from 'clsx'
import { Newspaper, CheckCircle2, AlertCircle, XCircle } from 'lucide-react'
import type { NewsImpactResult } from '../../api/types'
import NewsImpactRow from './NewsImpactRow'

const VERDICT_CONFIG = {
  supports: { label: '逻辑成立', cls: 'text-accent-green bg-accent-green/15', Icon: CheckCircle2 },
  partially: { label: '部分成立', cls: 'text-amber-400 bg-amber-400/15', Icon: AlertCircle },
  contradicts: { label: '逻辑存疑', cls: 'text-accent-red bg-accent-red/15', Icon: XCircle },
}

const HORIZON_LABEL: Record<string, string> = {
  short: '短期', mid: '中长线', long: '长期',
}

export default function NewsImpactCard({ data }: { data: NewsImpactResult }) {
  const verdict = VERDICT_CONFIG[data.logic_verdict] || VERDICT_CONFIG.partially
  const VerdictIcon = verdict.Icon
  const eventPriced = Math.round(data.event_priced_in_pct * 100)
  const dirLabel = data.user_direction === 'bullish' ? '利好' : '利空'

  return (
    <div className="mt-3 bg-surface border border-primary/30 rounded-xl p-4 max-w-md">
      <div className="flex items-center gap-2 mb-3">
        <Newspaper size={16} className="text-primary" />
        <span className="font-semibold text-sm">消息影响分析 · {data.name}</span>
        <span className="ml-auto text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded shrink-0">
          {HORIZON_LABEL[data.horizon] || data.horizon}视角
        </span>
      </div>

      {/* 消息判断：用户给了方向就显示"你的判断"，没给就是 Bobby 自己判的 */}
      <div className="bg-surface-lighter rounded-lg p-2.5 mb-3">
        <div className="text-[10px] text-text-secondary mb-1">
          {data.hypothesis_given ? '你的判断' : 'Bobby 判断'}
        </div>
        <p className="text-xs leading-snug mb-1.5">
          「{data.user_thesis}」—— {data.hypothesis_given ? '你认为是' : 'Bobby 判断为'}
          <span className="text-primary font-medium">{dirLabel}</span>
        </p>
        <div className="flex items-center gap-2">
          <span className={clsx('flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded', verdict.cls)}>
            <VerdictIcon size={10} />
            {verdict.label}
          </span>
        </div>
        <p className="text-[11px] text-text-secondary leading-snug mt-1.5">{data.logic_assessment}</p>
      </div>

      {/* 这条消息的已定价程度 */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-text-secondary">这条消息当前已定价程度</span>
          <span className="text-xs font-semibold tabular-nums">{eventPriced}%</span>
        </div>
        <div className="h-1.5 bg-surface rounded-full overflow-hidden">
          <div
            className={clsx(
              'h-full rounded-full',
              eventPriced >= 66 ? 'bg-accent-red' : eventPriced >= 33 ? 'bg-amber-400' : 'bg-accent-green',
            )}
            style={{ width: `${eventPriced}%` }}
          />
        </div>
        <p className="text-[10px] text-text-secondary mt-0.5">
          {eventPriced >= 66 ? '已大幅定价 —— 消息可能不再是有效入场理由' : eventPriced >= 33 ? '部分定价 —— 仍有部分预期差' : '尚未充分定价 —— 仍有空间'}
        </p>
      </div>

      {/* 更大范围检索到的影响消息 */}
      {data.related_news.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-text-secondary mb-1.5">
            更大范围检索 · {data.related_news.length} 条影响 {data.name} 的消息
          </div>
          <div className="space-y-1.5">
            {data.related_news.map((item, i) => (
              <NewsImpactRow key={i} item={item} />
            ))}
          </div>
        </div>
      )}

      {data.summary && (
        <p className="text-xs text-text-secondary leading-relaxed border-t border-border pt-2">
          {data.summary}
        </p>
      )}
    </div>
  )
}
