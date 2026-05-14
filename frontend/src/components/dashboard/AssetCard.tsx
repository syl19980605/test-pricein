import type { Asset, Signal } from '../../api/types'
import SparkLine from '../common/SparkLine'
import { SignalBadge } from '../common/Badge'
import clsx from 'clsx'

const CLASS_LABELS: Record<string, string> = {
  a_share: 'A股',
  us_stock: '美股',
  crypto: '加密',
  commodity: '商品',
}

const CLASS_COLORS: Record<string, string> = {
  a_share: 'bg-red-500/20 text-red-400',
  us_stock: 'bg-blue-500/20 text-blue-400',
  crypto: 'bg-amber-500/20 text-amber-400',
  commodity: 'bg-yellow-500/20 text-yellow-400',
}

function formatPrice(price: number): string {
  if (price >= 10000) return price.toLocaleString('en-US', { maximumFractionDigits: 0 })
  if (price >= 1) return price.toFixed(2)
  return price.toFixed(4)
}

function formatMarketCap(cap: number | null): string {
  if (!cap) return '-'
  if (cap >= 1e12) return `$${(cap / 1e12).toFixed(1)}T`
  if (cap >= 1e9) return `$${(cap / 1e9).toFixed(1)}B`
  if (cap >= 1e6) return `$${(cap / 1e6).toFixed(1)}M`
  return `$${cap.toLocaleString()}`
}

interface AssetCardProps {
  asset: Asset
  signal?: Signal
}

export default function AssetCard({ asset, signal }: AssetCardProps) {
  const isPositive = asset.change_24h_pct >= 0

  return (
    <div className="bg-surface-light border border-border rounded-2xl p-5 hover:border-primary/50 transition-all">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-text-primary">{asset.name}</span>
            <span className={clsx('text-[10px] px-1.5 py-0.5 rounded-full font-medium', CLASS_COLORS[asset.asset_class])}>
              {CLASS_LABELS[asset.asset_class]}
            </span>
          </div>
          <span className="text-xs text-text-secondary">{asset.symbol}</span>
        </div>
        <SparkLine data={asset.price_history_7d} width={80} height={28} />
      </div>

      <div className="flex items-end justify-between mb-3">
        <div>
          <div className="text-2xl font-bold tracking-tight">
            {asset.asset_class === 'a_share' ? '¥' : '$'}{formatPrice(asset.current_price)}
          </div>
          <div className="text-xs text-text-secondary mt-1">
            MCap {formatMarketCap(asset.market_cap)}
          </div>
        </div>
        <div className={clsx(
          'text-sm font-semibold px-2.5 py-1 rounded-lg',
          isPositive ? 'bg-accent-green/15 text-accent-green' : 'bg-accent-red/15 text-accent-red'
        )}>
          {isPositive ? '+' : ''}{asset.change_24h_pct.toFixed(2)}%
        </div>
      </div>

      <div className="border-t border-border pt-3 flex items-center justify-between">
        {signal ? (
          <>
            <SignalBadge direction={signal.direction} />
            <div className="flex items-center gap-1.5 text-[10px] text-text-secondary">
              <span>已定价</span>
              <div className="w-12 h-1 bg-surface rounded-full overflow-hidden">
                <div
                  className="h-full bg-amber-400 rounded-full"
                  style={{ width: `${signal.priced_in_score * 100}%` }}
                />
              </div>
              <span className="tabular-nums">{(signal.priced_in_score * 100).toFixed(0)}%</span>
            </div>
          </>
        ) : (
          <span className="text-[10px] text-text-secondary">信号待生成 — 在 Bobby 对话中询问该资产</span>
        )}
      </div>
    </div>
  )
}
