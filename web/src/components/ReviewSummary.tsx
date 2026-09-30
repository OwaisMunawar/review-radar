import type { ReactNode } from 'react'

import type { Review } from '../api/types'
import { STORE_LABELS, formatDate } from '../lib/format'
import { CategoryBadge, SentimentBadge, SeverityBadge } from './badges'
import { Stars } from './Stars'

/** The one way a review is shown: explorer rows, theme samples and the reply queue. */
export function ReviewSummary({ review, footer }: { review: Review; footer?: ReactNode }) {
  return (
    <article className="space-y-2">
      <div className="text-muted flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
        <Stars rating={review.rating} />
        <span>{STORE_LABELS[review.store]}</span>
        {review.app_version && <span>v{review.app_version}</span>}
        {review.language && <span className="uppercase">{review.language}</span>}
        <time dateTime={review.created_at}>{formatDate(review.created_at)}</time>
      </div>
      {review.title && <h3 className="text-ink font-medium">{review.title}</h3>}
      <p className="text-ink-2 text-sm">{review.body}</p>
      {review.triage && (
        <div className="flex flex-wrap items-center gap-1.5">
          <CategoryBadge category={review.triage.category} />
          <SentimentBadge sentiment={review.triage.sentiment} />
          <SeverityBadge severity={review.triage.severity} />
          <span className="text-muted text-xs">{review.triage.summary}</span>
        </div>
      )}
      {footer}
    </article>
  )
}
