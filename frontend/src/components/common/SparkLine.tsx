interface SparkLineProps {
  data: number[]
  width?: number
  height?: number
  color?: string
}

export default function SparkLine({ data, width = 100, height = 32, color }: SparkLineProps) {
  if (!data || data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  const lineColor = color || (data[data.length - 1] >= data[0] ? '#22c55e' : '#ef4444')

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width
    const y = height - ((val - min) / range) * (height - 4) - 2
    return `${x},${y}`
  }).join(' ')

  return (
    <svg width={width} height={height} className="inline-block">
      <polyline
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  )
}
