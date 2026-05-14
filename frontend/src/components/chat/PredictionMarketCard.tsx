import clsx from 'clsx'
import { Scale, ExternalLink, AlertTriangle, Search } from 'lucide-react'
import type { PredictionMarketBasket } from '../../api/types'

const RISK_CONFIG = {
  high: { label: '卖事实风险高', cls: 'text-accent-red bg-accent-red/15' },
  medium: { label: '部分预期', cls: 'text-amber-400 bg-amber-400/15' },
  low: { label: '尚未定价', cls: 'text-accent-green bg-accent-green/15' },
}

const HORIZON_LABEL: Record<string, string> = {
  short: '短期', mid: '中长线', long: '长期',
}

export default function PredictionMarketCard({ data }: { data: PredictionMarketBasket }) {
  const aggPct = Math.round(data.aggregate_priced_in * 100)
  const confPct = Math.round(data.overall_confidence * 100)

  return (
    <div className="mt-3 bg-gradient-to-br from-primary/15 via-surface to-surface border border-primary/50 rounded-xl p-4 max-w-lg">
      {/* 头部：强调这是和传统量化最不一样的维度 */}
      <div className="flex items-center gap-2 mb-1">
        <div className="w-7 h-7 rounded-lg bg-primary/25 flex items-center justify-center">
          <Scale size={15} className="text-primary" />
        </div>
        <div className="flex-1">
          <div className="font-bold text-sm">预测市场定价</div>
          <div className="text-[10px] text-text-secondary">市场用真金白银投出的「预期」—— 技术指标看不到的维度</div>
        </div>
        <span className="text-[10px] bg-primary/20 text-primary px-1.5 py-0.5 rounded shrink-0">
          {HORIZON_LABEL[data.horizon] || data.horizon}视角
        </span>
      </div>

      {!data.matched ? (
        <div className="mt-3 bg-surface rounded-lg p-3 border border-border">
          {data.factors_searched.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-2">
              <span className="text-[10px] text-text-secondary flex items-center gap-1">
                <Search size={9} /> 已检索:
              </span>
              {data.factors_searched.map((f, i) => (
                <span key={i} className="text-[10px] bg-surface-lighter px-1.5 py-0.5 rounded text-text-secondary">
                  {f}
                </span>
              ))}
            </div>
          )}
          <p className="text-xs text-text-secondary leading-snug">{data.reason || '暂无对应的预测市场覆盖'}</p>
        </div>
      ) : (
        <>
          {/* 聚合定价度 —— hero 数字 */}
          <div className="flex items-end gap-4 mt-3 mb-2 bg-surface/60 rounded-lg p-3">
            <div>
              <div className="text-3xl font-bold tabular-nums leading-none text-primary">{aggPct}%</div>
              <div className="text-[10px] text-text-secondary mt-1">关键预期整体已定价程度</div>
            </div>
            <div className="flex-1 text-[11px] text-text-secondary leading-snug pb-0.5">
              {aggPct >= 66
                ? '驱动因素的预期大多已被市场消化 —— 兑现时「卖事实」风险高'
                : aggPct >= 40
                ? '部分预期已定价，仍有未被充分消化的驱动因素'
                : '关键预期尚未被市场充分定价 —— 预期差仍在'}
            </div>
          </div>

          {/* 公式 + 整体可信度 */}
          <div className="text-[10px] text-text-secondary mb-2 bg-surface/40 rounded px-2 py-1 leading-relaxed">
            <span className="font-mono">aggregate = Σ(P·r·c·h) / Σ(r·c·h)</span>
            ，整体可信度 <span className="font-medium text-text-primary">{confPct}%</span>
            （基于成交量与新鲜度）
          </div>

          {/* 拆解的驱动因素 */}
          <div className="flex flex-wrap items-center gap-1 mb-2">
            <span className="text-[10px] text-text-secondary flex items-center gap-1">
              <Search size={9} /> 拆解驱动因素:
            </span>
            {data.factors_searched.map((f, i) => (
              <span key={i} className="text-[10px] bg-surface-lighter px-1.5 py-0.5 rounded text-text-secondary">
                {f}
              </span>
            ))}
          </div>

          {/* 篮子：每个匹配到的市场 + 权重拆解 */}
          <div className="space-y-1.5 mb-3">
            {data.items.map((item, i) => {
              const pct = Math.round(item.probability * 100)
              const risk = RISK_CONFIG[item.sell_the_fact_risk] || RISK_CONFIG.low
              return (
                <div key={i} className="bg-surface rounded-lg p-2.5 border border-border">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-primary/20 text-primary shrink-0">
                      {item.factor}
                    </span>
                    {item.slug && (
                      <a
                        href={`https://polymarket.com/event/${item.slug}`}
                        target="_blank"
                        rel="noreferrer"
                        className="ml-auto text-text-secondary hover:text-primary shrink-0"
                      >
                        <ExternalLink size={10} />
                      </a>
                    )}
                  </div>
                  <p className="text-[11px] text-text-secondary leading-snug mb-1.5">「{item.market_question}」</p>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-base font-bold tabular-nums">{pct}%</span>
                    <div className="flex-1 h-1.5 bg-surface-lighter rounded-full overflow-hidden">
                      <div
                        className={clsx(
                          'h-full rounded-full',
                          pct >= 66 ? 'bg-accent-red' : pct >= 40 ? 'bg-amber-400' : 'bg-accent-green',
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <span className={clsx('flex items-center gap-0.5 text-[9px] font-medium px-1.5 py-0.5 rounded shrink-0', risk.cls)}>
                      {item.sell_the_fact_risk === 'high' && <AlertTriangle size={8} />}
                      {risk.label}
                    </span>
                  </div>
                  {/* 权重拆解：r·c·h */}
                  <div className="flex items-center gap-2 text-[9px] text-text-secondary">
                    <span>相关性 r={item.relevance.toFixed(2)}</span>
                    <span>·</span>
                    <span>置信度 c={item.confidence.toFixed(2)}</span>
                    <span>·</span>
                    <span>期限匹配 h={item.horizon_match.toFixed(2)}</span>
                    <span className="ml-auto font-medium text-text-primary">权重 {item.weight.toFixed(3)}</span>
                  </div>
                </div>
              )
            })}
          </div>

          {data.summary && (
            <p className="text-xs text-text-secondary leading-relaxed border-t border-primary/20 pt-2">
              {data.summary}
            </p>
          )}
        </>
      )}
    </div>
  )
}
