import { Radar, RefreshCw } from 'lucide-react'
import type { Monitor } from '../../api/types'
import { SignalBadge } from '../common/Badge'
import NewsImpactRow from './NewsImpactRow'

function intervalLabel(min: number): string {
  if (min >= 1440) return `每 ${Math.round(min / 1440)} 天`
  if (min >= 60) return `每 ${Math.round(min / 60)} 小时`
  return `每 ${min} 分钟`
}

export default function MonitorCard({ data }: { data: Monitor }) {
  const dirLabel = data.direction === 'bullish' ? '看多' : '看空'

  return (
    <div className="mt-3 bg-surface border border-accent-green/30 rounded-xl p-4 max-w-md">
      <div className="flex items-center gap-2 mb-1">
        <Radar size={16} className="text-accent-green" />
        <span className="font-semibold text-sm">监控已创建 · {data.name}</span>
      </div>
      <div className="flex items-center gap-2 mb-3 text-[10px] text-text-secondary">
        <span className="flex items-center gap-1">
          <RefreshCw size={9} />
          {intervalLabel(data.refresh_interval_min)}刷新
        </span>
        <span>·</span>
        <span>你的判断：{dirLabel}</span>
      </div>

      {/* 综合信号 */}
      {data.signal_direction && (
        <div className="flex items-center justify-between bg-surface-lighter rounded-lg p-2.5 mb-3">
          <span className="text-xs text-text-secondary">当前综合信号</span>
          <div className="flex items-center gap-2">
            <SignalBadge direction={data.signal_direction} />
            {data.signal_priced_in !== null && (
              <span className="text-[10px] text-text-secondary">
                已定价 {Math.round((data.signal_priced_in ?? 0) * 100)}%
              </span>
            )}
          </div>
        </div>
      )}

      {/* 截至当前的价格影响消息 */}
      {data.news.length > 0 && (
        <div className="mb-2">
          <div className="text-xs text-text-secondary mb-1.5">
            截至当前 · {data.news.length} 条价格影响消息
          </div>
          <div className="space-y-1.5">
            {data.news.map((item, i) => (
              <NewsImpactRow key={i} item={item} />
            ))}
          </div>
        </div>
      )}

      <p className="text-[10px] text-text-secondary border-t border-border pt-2">
        监控已加入「监控」页，会按设定周期自动刷新消息与定价程度。
      </p>
    </div>
  )
}
