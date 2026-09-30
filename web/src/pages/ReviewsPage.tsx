import { useState } from 'react'
import { useSearchParams } from 'react-router'

import { useReleases, useReviews } from '../api/hooks'
import type { Category, ReviewQuery, Sentiment, Severity, Store } from '../api/types'
import { ReviewSummary } from '../components/ReviewSummary'
import { ReplyStateBadge } from '../components/badges'
import { Card, EmptyState, PageHeader, Pagination, QueryState, SelectField } from '../components/ui'
import {
  CATEGORY_LABELS,
  SENTIMENT_LABELS,
  SEVERITY_LABELS,
  STORE_LABELS,
  formatInt,
} from '../lib/format'

const PAGE = 20
const options = <K extends string>(labels: Record<K, string>) =>
  (Object.entries(labels) as [K, string][]).map(([value, label]) => ({ value, label }))

type FilterKey = 'store' | 'category' | 'sentiment' | 'severity' | 'version' | 'theme_id' | 'q'

export function ReviewsPage() {
  // Filters live in the URL so a filtered view can be shared or bookmarked.
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState(params.get('q') ?? '')
  const releases = useReleases()
  const get = (key: FilterKey) => params.get(key) ?? undefined
  const offset = Number(params.get('offset') ?? 0)

  const query: ReviewQuery = {
    store: get('store') as Store | undefined,
    category: get('category') as Category | undefined,
    sentiment: get('sentiment') as Sentiment | undefined,
    severity: get('severity') as Severity | undefined,
    version: get('version'),
    theme_id: get('theme_id'),
    q: get('q'),
    limit: PAGE,
    offset,
  }
  const reviews = useReviews(query)

  const update = (key: FilterKey | 'offset', value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    if (key !== 'offset') next.delete('offset')
    setParams(next)
  }

  return (
    <>
      <PageHeader
        title="Review explorer"
        description="Every review with its triage. Filter by store, category, sentiment, severity or release."
      />
      <Card className="mb-6">
        <form
          role="search"
          className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6"
          onSubmit={(event) => {
            event.preventDefault()
            update('q', search.trim())
          }}
        >
          <SelectField
            label="Store"
            options={options(STORE_LABELS)}
            value={get('store') ?? ''}
            onValueChange={(v) => {
              update('store', v)
            }}
          />
          <SelectField
            label="Category"
            options={options(CATEGORY_LABELS)}
            value={get('category') ?? ''}
            onValueChange={(v) => {
              update('category', v)
            }}
          />
          <SelectField
            label="Sentiment"
            options={options(SENTIMENT_LABELS)}
            value={get('sentiment') ?? ''}
            onValueChange={(v) => {
              update('sentiment', v)
            }}
          />
          <SelectField
            label="Severity"
            options={options(SEVERITY_LABELS)}
            value={get('severity') ?? ''}
            onValueChange={(v) => {
              update('severity', v)
            }}
          />
          <SelectField
            label="Release"
            options={(releases.data ?? []).map((r) => ({ value: r.version, label: r.version }))}
            value={get('version') ?? ''}
            onValueChange={(v) => {
              update('version', v)
            }}
          />
          <div className="flex flex-col gap-1">
            <label htmlFor="review-search" className="text-muted text-xs font-medium">
              Search
            </label>
            <input
              id="review-search"
              type="search"
              value={search}
              placeholder="Text or summary"
              maxLength={200}
              className="border-line bg-surface text-ink placeholder:text-muted h-9 rounded-md border px-2 text-sm"
              onChange={(event) => {
                setSearch(event.target.value)
              }}
            />
          </div>
        </form>
        {get('theme_id') && (
          <p className="text-ink-2 mt-3 text-sm">
            Showing one theme.{' '}
            <button
              type="button"
              className="text-accent hover:underline"
              onClick={() => {
                update('theme_id', '')
              }}
            >
              Clear
            </button>
          </p>
        )}
      </Card>

      <QueryState query={reviews}>
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState title="No reviews match these filters" />
          ) : (
            <Card title={`${formatInt(page.total)} reviews`}>
              <ul className="divide-line divide-y">
                {page.items.map((review) => (
                  <li key={review.id} className="py-4 first:pt-0">
                    <ReviewSummary
                      review={review}
                      footer={
                        (review.theme_title ?? review.reply_state) && (
                          <div className="text-muted flex items-center gap-2 text-xs">
                            {review.theme_title && <span>Theme: {review.theme_title}</span>}
                            {review.reply_state && <ReplyStateBadge state={review.reply_state} />}
                          </div>
                        )
                      }
                    />
                  </li>
                ))}
              </ul>
              <Pagination
                total={page.total}
                limit={page.limit}
                offset={page.offset}
                onChange={(next) => {
                  update('offset', String(next))
                }}
              />
            </Card>
          )
        }
      </QueryState>
    </>
  )
}
