interface SparklineProps {
  values: number[]
  label: string
  width?: number
  height?: number
}

/** Tiny trend line with an end dot. The accessible name carries the numbers. */
export function Sparkline({ values, label, width = 120, height = 32 }: SparklineProps) {
  if (values.length < 2) return null
  const max = Math.max(...values, 1)
  const step = width / (values.length - 1)
  const pad = 3
  const y = (v: number) => height - pad - (v / max) * (height - pad * 2)
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const last = values[values.length - 1] ?? 0
  return (
    <svg
      width={width}
      height={height}
      viewBox={`-3 0 ${width + 6} ${height}`}
      role="img"
      aria-label={`${label}: ${values.join(', ')}`}
    >
      <title>{`${label}: ${values.join(', ')}`}</title>
      <polyline
        points={points}
        fill="none"
        stroke="var(--series-1)"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle
        cx={width}
        cy={y(last)}
        r="3"
        fill="var(--series-1)"
        stroke="var(--surface)"
        strokeWidth="2"
      />
    </svg>
  )
}
