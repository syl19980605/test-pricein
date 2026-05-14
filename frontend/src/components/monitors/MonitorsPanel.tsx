import { useEffect, useState } from 'react'
import { fetchMonitors, refreshMonitor } from '../../api/client'
import type { Monitor } from '../../api/types'
import { Radar, RefreshCw, Loader2, Hourglass } from 'lucide-react'
import clsx from 'clsx'
import { SignalBadge } from '../common/Badge'
import NewsImpactRow from '../chat/NewsImpactRow'

const HORIZON_LABELS: Record<string, string> = {
  short: '短期',
  mid: '中长线',
  long: '长期',
}

function intervalLabel(min: number): string {
  if (min >= 1440) return `每 ${Math.round(min / 1440)} 天`
  if (min >= 60) return `每 ${Math.round(min / 60)} 小时`
  return `每 ${min} 分钟`
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso.replace(' ', 'T') + 'Z').getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}小时前`
  return `${Math.floor(hrs / 24)}天前`
}

export default function MonitorsPanel() {
  const [monitors, setMonitors] = useState<Monitor[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState<string | null>(null)

  const load = () =>
    fetchMonitors()
      .then(setMonitors)
      .catch(() => {})
      .finally(() => setLoading(false))

  useEffect(() => {
    load()
    const interval = setInterval(load, 60000)
    return () => clearInterval(interval)
  }, [])

  const handleRefresh = async (id: string) => {
    setRefreshing(id)
    try {
      const updated = await refreshMonitor(id)
      setMonitors(prev => prev.map(m => (m.id === id ? updated : m)))
    } catch {
      // ignore
    } finally {
      setRefreshing(null)
    }
  }

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
        <h2 className="text-xl font-bold">标的监控</h2>
        <p className="text-sm text-text-secondary mt-1">
          在 Bobby 对话中创建的监控会出现在这里 — 按设定周期自动刷新价格影响消息、信号与定价程度
        </p>
      </div>

      {monitors.length === 0 ? (
        <div className="bg-surface-light border border-border rounded-2xl p-12 text-center">
          <Radar size={32} className="text-text-secondary mx-auto mb-3" />
          <p className="text-text-secondary text-sm">
            还没有监控。在 Bobby 对话里描述一条消息（如「我看到英伟达获批向中国销售H200，我觉得是利好」），
            分析后点「创建监控」即可。
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {monitors.map(m => (
            <div key={m.id} className="bg-surface-light border border-border rounded-2xl p-5">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <Radar size={15} className="text-accent-green" />
                    <span className="font-semibold">{m.name}</span>
                    <span className="text-xs text-text-secondary">{m.symbol}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1 text-[10px] text-text-secondary">
                    <span>{intervalLabel(m.refresh_interval_min)}刷新</span>
                    <span>·</span>
                    <span>{timeAgo(m.last_refreshed_at)}更新</span>
                    <span>·</span>
                    <span>你的判断：{m.direction === 'bullish' ? '看多' : '看空'}</span>
                  </div>
                </div>
                <button
                  onClick={() => handleRefresh(m.id)}
                  disabled={refreshing === m.id}
                  className="flex items-center gap-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-40 transition-colors cursor-pointer"
                >
                  <RefreshCw size={12} className={clsx(refreshing === m.id && 'animate-spin')} />
                  刷新
                </button>
              </div>

              {m.thesis && (
                <p className="text-xs text-text-secondary bg-surface rounded-lg p-2 mb-3 leading-snug">
                  「{m.thesis}」
                </p>
              )}

              <div className="flex items-center gap-3 mb-3">
                {m.signal_direction && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-text-secondary">综合信号</span>
                    <SignalBadge direction={m.signal_direction} />
                  </div>
                )}
                {m.signal_priced_in !== null && (
                  <span className="text-[10px] text-text-secondary">
                    已定价 {Math.round((m.signal_priced_in ?? 0) * 100)}%
                  </span>
                )}
                {m.horizon && (
                  <span className="flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-primary/15 text-primary">
                    <Hourglass size={9} />
                    {HORIZON_LABELS[m.horizon]}视角
                  </span>
                )}
              </div>

              {m.news.length > 0 ? (
                <div className="space-y-1.5">
                  <div className="text-[10px] text-text-secondary">
                    截至当前 · {m.news.length} 条价格影响消息
                  </div>
                  {m.news.map((item, i) => (
                    <NewsImpactRow key={i} item={item} />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-text-secondary">暂无影响消息</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
