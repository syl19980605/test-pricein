import { useEffect, useState } from 'react'
import { fetchAlerts } from '../../api/client'
import type { Alert } from '../../api/types'
import { Bell, AlertTriangle, Info, AlertOctagon } from 'lucide-react'
import clsx from 'clsx'

const SEVERITY_CONFIG = {
  info: { icon: Info, cls: 'text-blue-400 bg-blue-400/10' },
  warning: { icon: AlertTriangle, cls: 'text-amber-400 bg-amber-400/10' },
  critical: { icon: AlertOctagon, cls: 'text-accent-red bg-accent-red/10' },
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso + 'Z').getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}小时前`
  return `${Math.floor(hrs / 24)}天前`
}

export default function AlertsPanel() {
  const [alerts, setAlerts] = useState<Alert[]>([])

  useEffect(() => {
    const load = () => fetchAlerts().then(setAlerts).catch(() => {})
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="bg-surface-light border border-border rounded-2xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <Bell size={16} className="text-primary" />
        <h3 className="font-semibold">监控预警</h3>
        {alerts.length > 0 && (
          <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full ml-auto">
            {alerts.length}
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <p className="text-sm text-text-secondary py-8 text-center">
          暂无预警 — 后台监控每 5 分钟扫描一次价格异动、指标穿越和持仓止损
        </p>
      ) : (
        <div className="space-y-2 max-h-96 overflow-y-auto">
          {alerts.map(alert => {
            const cfg = SEVERITY_CONFIG[alert.severity]
            const Icon = cfg.icon
            return (
              <div
                key={alert.id}
                className="flex gap-3 p-3 bg-surface rounded-xl border border-border"
              >
                <div className={clsx('w-7 h-7 rounded-lg flex items-center justify-center shrink-0', cfg.cls)}>
                  <Icon size={14} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium truncate">{alert.title}</span>
                    <span className="text-[10px] text-text-secondary shrink-0">{timeAgo(alert.created_at)}</span>
                  </div>
                  <p className="text-xs text-text-secondary mt-0.5 leading-snug">{alert.message}</p>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
