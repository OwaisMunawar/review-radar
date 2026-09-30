export interface Bar {
  key: string
  label: string
  value: number
}

/** Horizontal bars with the value printed beside each label, so colour never carries meaning. */
export function BarList({
  bars,
  format = String,
}: {
  bars: Bar[]
  format?: (n: number) => string
}) {
  const max = Math.max(...bars.map((b) => b.value), 1)
  return (
    <ul className="space-y-2.5">
      {bars.map((bar) => (
        <li key={bar.key}>
          <div className="mb-1 flex justify-between text-sm">
            <span className="text-ink-2">{bar.label}</span>
            <span className="tabular text-ink">{format(bar.value)}</span>
          </div>
          <div className="bg-surface-2 h-2 rounded-full">
            <div
              className="bg-series-1 h-2 rounded-full"
              style={{ width: `${Math.max(2, (bar.value / max) * 100)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  )
}
