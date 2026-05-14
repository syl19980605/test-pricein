import clsx from 'clsx'

interface ScoreBarProps {
  label: string
  value: number
  min?: number
  max?: number
  positiveColor?: string
  hint?: string
}

/** A horizontal bar showing a score. For -1..1 ranges, center is 0. For 0..1, fills from left. */
export default function ScoreBar({
  label,
  value,
  min = -1,
  max = 1,
  hint,
}: ScoreBarProps) {
  const range = max - min
  const pct = ((value - min) / range) * 100
  const isBipolar = min < 0

  let barColor = 'bg-primary'
  if (isBipolar) {
    barColor = value >= 0 ? 'bg-accent-green' : 'bg-accent-red'
  } else {
    if (value >= 0.66) barColor = 'bg-accent-red'
    else if (value >= 0.33) barColor = 'bg-amber-400'
    else barColor = 'bg-accent-green'
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-xs text-text-secondary">{label}</span>
        <span className="text-xs font-medium tabular-nums">
          {isBipolar && value >= 0 ? '+' : ''}{value.toFixed(2)}
        </span>
      </div>
      <div className="h-1.5 bg-surface rounded-full overflow-hidden relative">
        {isBipolar && (
          <div className="absolute left-1/2 top-0 bottom-0 w-px bg-border" />
        )}
        <div
          className={clsx('h-full rounded-full transition-all', barColor)}
          style={{ width: `${Math.max(2, Math.min(100, pct))}%` }}
        />
      </div>
      {hint && <p className="text-[10px] text-text-secondary mt-0.5">{hint}</p>}
    </div>
  )
}
