import type { HTMLAttributes, ReactNode } from 'react'

import { cn } from './cn'

interface CardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: ReactNode
  description?: ReactNode
  actions?: ReactNode
}

export function Card({ title, description, actions, className, children, ...props }: CardProps) {
  return (
    <section
      className={cn('border-line bg-surface rounded-xl border p-5 shadow-xs', className)}
      {...props}
    >
      {(title ?? actions) && (
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-ink text-sm font-semibold">{title}</h2>}
            {description && <p className="text-muted mt-0.5 text-sm">{description}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  )
}
