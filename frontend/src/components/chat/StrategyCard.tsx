import type { StrategyCardData } from '../../api/types'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { Sparkles, ArrowDownRight, ArrowUpRight } from 'lucide-react'

const COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ec4899', '#06b6d4', '#a855f7', '#ef4444']

const RISK_LABELS: Record<string, string> = {
  conservative: '保守型',
  moderate: '稳健型',
  aggressive: '进取型',
}

function pct(v: number | null): string {
  if (v === null || v === undefined) return '-'
  return `${(v * 100).toFixed(1)}%`
}

export default function StrategyCard({ data }: { data: StrategyCardData }) {
  const pieData = Object.entries(data.allocation).map(([name, value]) => ({ name, value }))

  return (
    <div className="mt-3 bg-gradient-to-br from-surface to-surface-light border border-primary/40 rounded-xl p-4 max-w-lg">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles size={16} className="text-primary" />
        <span className="font-semibold text-sm">{data.title}</span>
        <span className="text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded ml-auto">
          {RISK_LABELS[data.risk_level] || data.risk_level}
        </span>
      </div>

      <div className="flex gap-4 mb-3">
        <div className="w-28 h-28 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={pieData} dataKey="value" innerRadius={28} outerRadius={52} paddingAngle={2}>
                {pieData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1 space-y-1 self-center">
          {pieData.map((d, i) => (
            <div key={d.name} className="flex items-center gap-2 text-xs">
              <span className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
              <span className="text-text-secondary flex-1">{d.name}</span>
              <span className="font-medium tabular-nums">{(d.value * 100).toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="bg-surface rounded-lg p-2 text-center">
          <div className="text-[10px] text-text-secondary">预期年化</div>
          <div className="text-sm font-bold text-accent-green">{pct(data.expected_return_annual)}</div>
        </div>
        <div className="bg-surface rounded-lg p-2 text-center">
          <div className="text-[10px] text-text-secondary">最大回撤</div>
          <div className="text-sm font-bold text-accent-red">{pct(data.max_drawdown)}</div>
        </div>
        <div className="bg-surface rounded-lg p-2 text-center">
          <div className="text-[10px] text-text-secondary">夏普比率</div>
          <div className="text-sm font-bold">{data.sharpe_ratio?.toFixed(2) ?? '-'}</div>
        </div>
      </div>

      {data.reasoning && (
        <p className="text-xs text-text-secondary leading-relaxed mb-3">{data.reasoning}</p>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <div className="flex items-center gap-1 text-xs font-medium text-accent-green mb-1">
            <ArrowUpRight size={12} /> 进场条件
          </div>
          <ul className="space-y-1">
            {data.entry_conditions.map((c, i) => (
              <li key={i} className="text-[11px] text-text-secondary leading-snug">· {c}</li>
            ))}
          </ul>
        </div>
        <div>
          <div className="flex items-center gap-1 text-xs font-medium text-accent-red mb-1">
            <ArrowDownRight size={12} /> 出场条件
          </div>
          <ul className="space-y-1">
            {data.exit_conditions.map((c, i) => (
              <li key={i} className="text-[11px] text-text-secondary leading-snug">· {c}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
