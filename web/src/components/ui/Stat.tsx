import type { ReactNode } from 'react'

import { Card } from './Card'

interface StatProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  chart?: ReactNode
}

/** A KPI tile: one number, what it means, and optionally its recent shape. */
export function Stat({ label, value, hint, chart }: StatProps) {
  return (
    <Card className="flex flex-col gap-2">
      <p className="text-muted text-sm">{label}</p>
      <p className="text-ink text-3xl font-semibold tracking-tight">{value}</p>
      {hint && <p className="text-ink-2 text-sm">{hint}</p>}
      {chart && <div className="mt-auto pt-2">{chart}</div>}
    </Card>
  )
}
