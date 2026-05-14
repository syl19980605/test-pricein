import clsx from 'clsx'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { NewsImpactItem } from '../../api/types'

const DIRECTION_CONFIG = {
  bullish: { label: '利好', cls: 'text-accent-green bg-accent-green/15', Icon: TrendingUp },
  bearish: { label: '利空', cls: 'text-accent-red bg-accent-red/15', Icon: TrendingDown },
  neutral: { label: '中性', cls: 'text-slate-300 bg-slate-500/20', Icon: Minus },
}

const HORIZON_LABELS: Record<string, string> = {
  short: '短期',
  mid: '中长线',
  long: '长期',
}

export default function NewsImpactRow({ item }: { item: NewsImpactItem }) {
  const dir = DIRECTION_CONFIG[item.impact_direction] || DIRECTION_CONFIG.neutral
  const DirIcon = dir.Icon
  const pricedPct = Math.round(item.priced_in_pct * 100)

  return (
    <div className="bg-surface rounded-lg p-2.5 border border-border">
      <div className="flex items-start gap-2 mb-1">
        <span className={clsx('flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded shrink-0', dir.cls)}>
          <DirIcon size={9} />
          {dir.label}
        </span>
        {item.horizon && (
          <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-primary/15 text-primary shrink-0">
            {HORIZON_LABELS[item.horizon] || item.horizon}
          </span>
        )}
        <span className="text-xs font-medium leading-snug flex-1">{item.title}</span>
      </div>
      {item.impact_summary && (
        <p className="text-[11px] text-text-secondary leading-snug mb-1.5 pl-0.5">{item.impact_summary}</p>
      )}
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] text-text-secondary">已定价</span>
        <div className="flex-1 h-1 bg-surface-lighter rounded-full overflow-hidden">
          <div
            className={clsx(
              'h-full rounded-full',
              pricedPct >= 66 ? 'bg-accent-red' : pricedPct >= 33 ? 'bg-amber-400' : 'bg-accent-green',
            )}
            style={{ width: `${pricedPct}%` }}
          />
        </div>
        <span className="text-[10px] tabular-nums text-text-secondary w-8 text-right">{pricedPct}%</span>
      </div>
    </div>
  )
}
