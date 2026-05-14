import clsx from 'clsx'
import type { SignalDirection } from '../../api/types'

const DIRECTION_CONFIG: Record<SignalDirection, { label: string; cls: string }> = {
  strong_buy: { label: '强力买入', cls: 'bg-accent-green/20 text-accent-green' },
  buy: { label: '买入', cls: 'bg-accent-green/15 text-accent-green' },
  neutral: { label: '中性', cls: 'bg-slate-500/20 text-slate-300' },
  sell: { label: '卖出', cls: 'bg-accent-red/15 text-accent-red' },
  strong_sell: { label: '强力卖出', cls: 'bg-accent-red/20 text-accent-red' },
}

export function SignalBadge({ direction }: { direction: SignalDirection }) {
  const cfg = DIRECTION_CONFIG[direction]
  return (
    <span className={clsx('text-xs font-semibold px-2.5 py-1 rounded-lg', cfg.cls)}>
      {cfg.label}
    </span>
  )
}

export function getDirectionLabel(direction: SignalDirection): string {
  return DIRECTION_CONFIG[direction].label
}
