import { useEffect, useState } from 'react'
import { fetchAssets, fetchSignals } from '../../api/client'
import type { Asset, Signal } from '../../api/types'
import AssetCard from './AssetCard'
import AlertsPanel from './AlertsPanel'
import { RefreshCw, Loader2 } from 'lucide-react'

export default function DashboardPanel() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [signals, setSignals] = useState<Record<string, Signal>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadAssets = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchAssets()
      setAssets(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load assets')
    } finally {
      setLoading(false)
    }
  }

  const loadSignals = async () => {
    try {
      const data = await fetchSignals()
      const map: Record<string, Signal> = {}
      for (const s of data) map[s.symbol] = s
      setSignals(map)
    } catch {
      // signals are optional enrichment
    }
  }

  useEffect(() => {
    loadAssets()
    loadSignals()
    const interval = setInterval(() => {
      loadAssets()
      loadSignals()
    }, 60000)
    return () => clearInterval(interval)
  }, [])

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-accent-red">
        <p>{error}</p>
        <button onClick={loadAssets} className="mt-4 text-primary hover:underline cursor-pointer">
          重试
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold">头部资产监控</h2>
          <p className="text-sm text-text-secondary mt-1">
            实时跟踪 {assets.length} 个主流头部资产 — A股 / 美股 / 加密 / 商品
          </p>
        </div>
        <button
          onClick={() => { loadAssets(); loadSignals() }}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 rounded-xl bg-surface-lighter text-text-secondary hover:text-text-primary transition-colors text-sm cursor-pointer disabled:opacity-50"
        >
          {loading ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
          刷新
        </button>
      </div>

      {loading && assets.length === 0 ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 size={32} className="animate-spin text-primary" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4 content-start">
            {assets.map(asset => (
              <AssetCard key={asset.symbol} asset={asset} signal={signals[asset.symbol]} />
            ))}
          </div>
          <div className="lg:col-span-1">
            <AlertsPanel />
          </div>
        </div>
      )}
    </div>
  )
}
