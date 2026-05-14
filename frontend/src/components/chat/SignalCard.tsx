import type { Signal } from '../../api/types'
import { SignalBadge } from '../common/Badge'
import ScoreBar from '../common/ScoreBar'
import { TrendingUp } from 'lucide-react'

export default function SignalCard({ data }: { data: Signal }) {
  return (
    <div className="mt-3 bg-surface border border-primary/30 rounded-xl p-4 max-w-md">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <TrendingUp size={16} className="text-primary" />
          <span className="font-semibold text-sm">{data.symbol} 综合信号</span>
        </div>
        <SignalBadge direction={data.direction} />
      </div>

      <div className="space-y-2.5 mb-3">
        <ScoreBar label="技术面" value={data.technical_score} />
        <ScoreBar label="情绪面" value={data.sentiment_score} />
        <ScoreBar
          label="已定价程度"
          value={data.priced_in_score}
          min={0}
          max={1}
          hint="越高 = 消息越可能已反映在价格中，情绪面影响被削弱"
        />
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs text-text-secondary">置信度</span>
        <div className="flex-1 h-1 bg-surface-lighter rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full"
            style={{ width: `${data.confidence * 100}%` }}
          />
        </div>
        <span className="text-xs tabular-nums">{(data.confidence * 100).toFixed(0)}%</span>
      </div>

      {data.key_factors.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {data.key_factors.map((f, i) => (
            <span key={i} className="text-[10px] bg-surface-lighter px-1.5 py-0.5 rounded text-text-secondary">
              {f}
            </span>
          ))}
        </div>
      )}

      <p className="text-xs text-text-secondary leading-relaxed border-t border-border pt-2">
        {data.reasoning}
      </p>
    </div>
  )
}
