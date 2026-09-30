import type { ReactNode } from 'react'

import { ApiError } from '../../api/client'
import { EmptyState } from './EmptyState'

interface QueryStateProps<T> {
  query: { data: T | undefined; isPending: boolean; error: Error | null }
  children: (data: T) => ReactNode
  loading?: ReactNode
}

/** Renders the loading and error branches once, so pages only describe the happy path. */
export function QueryState<T>({ query, children, loading }: QueryStateProps<T>) {
  if (query.error) {
    const message =
      query.error instanceof ApiError
        ? `${query.error.message} (${query.error.code})`
        : 'The API did not respond. Is the backend running?'
    return <EmptyState title="Could not load this view">{message}</EmptyState>
  }
  if (query.isPending || query.data === undefined) {
    return (
      loading ?? (
        <div role="status" className="animate-pulse space-y-3" aria-label="Loading">
          <div className="bg-surface-2 h-4 w-1/3 rounded" />
          <div className="bg-surface-2 h-24 rounded" />
        </div>
      )
    )
  }
  return <>{children(query.data)}</>
}
