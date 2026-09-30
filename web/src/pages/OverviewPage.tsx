import { Link } from 'react-router'

import { useOverview, useRegressions } from '../api/hooks'
import type { Overview, Segment } from '../api/types'
import {
  BarList,
  Card,
  EmptyState,
  LineChart,
  PageHeader,
  QueryState,
  Sparkline,
  Stat,
} from '../components/ui'
import {
  CATEGORY_LABELS,
  STORE_LABELS,
  formatDecimal,
  formatInt,
  formatPercent,
  formatShortDate,
} from '../lib/format'

function Regressions({ flags }: { flags: Segment[] }) {
  if (flags.length === 0) {
    return (
      <EmptyState title="No regressions flagged">Every release is within its baseline.</EmptyState>
    )
  }
  return (
    <ul className="divide-line divide-y">
      {flags.map((flag) => (
        <li
          key={`${flag.key}-${flag.headline}`}
          className="flex items-center justify-between gap-4 py-2.5"
        >
          <div>
            <p className="text-bad font-medium">{flag.headline}</p>
            <p className="text-muted text-xs">
              {flag.baseline_count} → {flag.candidate_count} reviews · adjusted p{' '}
              {flag.adjusted_p_value < 0.0001 ? '< 0.0001' : flag.adjusted_p_value.toFixed(4)}
            </p>
          </div>
          <Link to="/releases" className="text-accent text-sm hover:underline">
            Compare
          </Link>
        </li>
      ))}
    </ul>
  )
}

function Dashboard({ data }: { data: Overview }) {
  const regressions = useRegressions()
  const weeks = data.weekly
  const ratingPoints = weeks.map((w) => ({
    label: formatShortDate(w.week_start),
    value: w.avg_rating,
  }))
  const volume = weeks.map((w) => w.reviews)
  const negative = weeks.map((w) => Math.round((w.negative_share ?? 0) * 100))
  const stores = Object.entries(data.stores)
    .map(
      ([store, count]) => `${STORE_LABELS[store as keyof typeof STORE_LABELS]} ${formatInt(count)}`,
    )
    .join(' · ')

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Reviews"
          value={formatInt(data.total_reviews)}
          hint={stores}
          chart={<Sparkline values={volume} label="Reviews per week" />}
        />
        <Stat
          label="Average rating"
          value={formatDecimal(data.avg_rating)}
          hint="out of 5, all stores"
          chart={
            <Sparkline
              values={weeks.map((w) => w.avg_rating ?? 0)}
              label="Average rating per week"
            />
          }
        />
        <Stat
          label="Negative"
          value={formatPercent(data.negative_share)}
          hint="share of triaged reviews"
          chart={<Sparkline values={negative} label="Negative share per week, percent" />}
        />
        <Stat
          label="Replies awaiting approval"
          value={formatInt(data.pending_replies)}
          hint={
            <Link to="/replies" className="text-accent hover:underline">
              Open the queue
            </Link>
          }
        />
      </div>

      <Card
        title="Regressions"
        description="Segments whose share of reviews jumped against the previous release."
      >
        <QueryState query={regressions}>{(flags) => <Regressions flags={flags} />}</QueryState>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card
          className="lg:col-span-2"
          title="Average rating by week"
          description="Hover for weekly values."
        >
          <LineChart
            points={ratingPoints}
            label="Average star rating per week"
            format={(v) => v.toFixed(1)}
            domain={[1, 5]}
          />
        </Card>
        <Card title="By category">
          <BarList
            bars={data.categories.map((c) => ({
              key: c.category,
              label: CATEGORY_LABELS[c.category],
              value: c.count,
            }))}
          />
        </Card>
      </div>

      <p className="text-muted text-xs">
        {formatInt(data.usage.calls)} model calls · {formatInt(data.usage.input_tokens)} input and{' '}
        {formatInt(data.usage.output_tokens)} output tokens · $
        {Number(data.usage.cost_usd).toFixed(4)} spent{data.demo_mode && ' (demo model, no cost)'}
      </p>
    </div>
  )
}

export function OverviewPage() {
  const overview = useOverview()
  return (
    <>
      <PageHeader
        title="Overview"
        description="Ratings, volume and sentiment across the App Store and Google Play, with release regressions flagged."
      />
      <QueryState query={overview}>{(data) => <Dashboard data={data} />}</QueryState>
    </>
  )
}
