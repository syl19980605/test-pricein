import { useEffect, useState } from 'react'
import { fetchPositions } from '../../api/client'
import type { Position } from '../../api/types'
import { Briefcase, Loader2 } from 'lucide-react'
import clsx from 'clsx'

export default function PositionsPanel() {
  const [positions, setPositions] = useState<Position[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = () =>
      fetchPositions()
        .then(setPositions)
        .catch(() => {})
        .finally(() => setLoading(false))
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  const open = positions.filter(p => p.status === 'open')
  const closed = positions.filter(p => p.status !== 'open')

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-bold">模拟持仓</h2>
        <p className="text-sm text-text-secondary mt-1">
          通过和 Bobby 对话开仓 — 后台监控会按设定的止盈止损纪律自动平仓
        </p>
      </div>

      {positions.length === 0 ? (
        <div className="bg-surface-light border border-border rounded-2xl p-12 text-center">
          <Briefcase size={32} className="text-text-secondary mx-auto mb-3" />
          <p className="text-text-secondary text-sm">
            还没有持仓。试着对 Bobby 说：「帮我模拟买入 1 股 NVDA，设 8% 止损 20% 止盈」
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {open.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-text-secondary mb-2">持仓中 ({open.length})</h3>
              <div className="space-y-2">
                {open.map(p => (
                  <PositionRow key={p.id} position={p} />
                ))}
              </div>
            </div>
          )}
          {closed.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-text-secondary mb-2">已平仓 ({closed.length})</h3>
              <div className="space-y-2">
                {closed.map(p => (
                  <PositionRow key={p.id} position={p} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const STATUS_LABELS: Record<string, string> = {
  open: '持仓中',
  closed_manual: '手动平仓',
  closed_sl: '止损平仓',
  closed_tp: '止盈平仓',
}

function PositionRow({ position: p }: { position: Position }) {
  const isProfit = p.pnl >= 0
  return (
    <div className="bg-surface-light border border-border rounded-xl p-4 flex items-center gap-4">
      <div className="w-24">
        <div className="font-semibold text-sm">{p.name}</div>
        <div className="text-xs text-text-secondary">{p.symbol}</div>
      </div>
      <div className={clsx(
        'text-xs px-2 py-0.5 rounded font-medium',
        p.direction === 'long' ? 'bg-accent-green/15 text-accent-green' : 'bg-accent-red/15 text-accent-red'
      )}>
        {p.direction === 'long' ? '多' : '空'}
      </div>
      <div className="text-xs text-text-secondary">
        入 {p.entry_price} → 现 {p.current_price}
      </div>
      <div className="text-xs text-text-secondary">
        {p.stop_loss && <span>止损 {p.stop_loss}</span>}
        {p.stop_loss && p.take_profit && ' · '}
        {p.take_profit && <span>止盈 {p.take_profit}</span>}
      </div>
      <div className="flex-1" />
      <div className={clsx('text-right', isProfit ? 'text-accent-green' : 'text-accent-red')}>
        <div className="font-bold tabular-nums">{isProfit ? '+' : ''}{p.pnl_pct.toFixed(2)}%</div>
        <div className="text-xs tabular-nums">{isProfit ? '+' : ''}{p.pnl.toFixed(2)}</div>
      </div>
      <div className="text-[10px] text-text-secondary w-16 text-right">
        {STATUS_LABELS[p.status] || p.status}
      </div>
    </div>
  )
}
