import type { ReactNode } from 'react'

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="border-line rounded-lg border border-dashed px-6 py-10 text-center">
      <p className="text-ink font-medium">{title}</p>
      {children && <div className="text-muted mt-1 text-sm">{children}</div>}
    </div>
  )
}
