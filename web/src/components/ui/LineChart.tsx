import { useId, useState } from 'react'

export interface Point {
  label: string
  value: number | null
}

interface LineChartProps {
  points: Point[]
  label: string
  format: (value: number) => string
  domain?: [number, number]
  height?: number
}

const WIDTH = 640
const PAD = { top: 12, right: 12, bottom: 24, left: 40 }

/**
 * A single-series line with a hover crosshair. Plain SVG: the dashboard needs
 * three chart shapes, which does not justify a charting dependency.
 */
export function LineChart({ points, label, format, domain, height = 200 }: LineChartProps) {
  const [active, setActive] = useState<number | null>(null)
  const titleId = useId()
  const values = points.map((p) => p.value).filter((v): v is number => v !== null)
  if (values.length === 0) return null

  const [lo, hi] = domain ?? [Math.min(0, ...values), Math.max(...values)]
  const innerW = WIDTH - PAD.left - PAD.right
  const innerH = height - PAD.top - PAD.bottom
  const x = (i: number) =>
    PAD.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW)
  const y = (v: number) => PAD.top + innerH - ((v - lo) / (hi - lo || 1)) * innerH
  const ticks = [lo, lo + (hi - lo) / 2, hi]

  const path = points
    .map((p, i) => (p.value === null ? null : `${x(i).toFixed(1)},${y(p.value).toFixed(1)}`))
    .filter(Boolean)
    .join(' ')
  const labelEvery = Math.ceil(points.length / 6)
  const hovered = active === null ? undefined : points[active]

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-labelledby={titleId}
        onMouseLeave={() => {
          setActive(null)
        }}
      >
        <title id={titleId}>{label}</title>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
            <text
              x={PAD.left - 8}
              y={y(t)}
              dy="0.32em"
              textAnchor="end"
              className="fill-muted text-[11px]"
            >
              {format(t)}
            </text>
          </g>
        ))}
        {points.map((p, i) =>
          i % labelEvery === 0 ? (
            <text
              key={p.label}
              x={x(i)}
              y={height - 6}
              textAnchor="middle"
              className="fill-muted text-[11px]"
            >
              {p.label}
            </text>
          ) : null,
        )}
        <polyline
          points={path}
          fill="none"
          stroke="var(--series-1)"
          strokeWidth="2"
          strokeLinejoin="round"
        />
        {hovered && active !== null && hovered.value !== null && (
          <g>
            <line
              x1={x(active)}
              x2={x(active)}
              y1={PAD.top}
              y2={PAD.top + innerH}
              stroke="var(--axis)"
            />
            <circle
              cx={x(active)}
              cy={y(hovered.value)}
              r="4"
              fill="var(--series-1)"
              stroke="var(--surface)"
              strokeWidth="2"
            />
          </g>
        )}
        {points.map((p, i) => (
          <rect
            key={p.label}
            x={x(i) - innerW / points.length / 2}
            y={PAD.top}
            width={innerW / points.length}
            height={innerH}
            fill="transparent"
            onMouseEnter={() => {
              setActive(i)
            }}
          />
        ))}
      </svg>
      {hovered && active !== null && (
        <div
          className="border-line bg-surface pointer-events-none absolute top-0 rounded-md border px-2 py-1 text-xs shadow-sm"
          style={{ left: `${(x(active) / WIDTH) * 100}%`, transform: 'translateX(-50%)' }}
        >
          <span className="text-muted">{hovered.label}</span>{' '}
          <span className="text-ink font-medium">
            {hovered.value === null ? '–' : format(hovered.value)}
          </span>
        </div>
      )}
    </div>
  )
}
