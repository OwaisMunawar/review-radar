import type { ReactNode } from 'react'

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-ink text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-ink-2 mt-1 max-w-2xl text-sm">{description}</p>}
      </div>
      {actions}
    </div>
  )
}
