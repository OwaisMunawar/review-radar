import { useSearchParams } from 'react-router'

import { useComparison, useReleases } from '../api/hooks'
import type { ReleaseComparison, Segment } from '../api/types'
import {
  Badge,
  Card,
  PageHeader,
  QueryState,
  SelectField,
  Stat,
  Table,
  type Column,
} from '../components/ui'
import { formatDecimal, formatPValue, formatPercent, formatRatio } from '../lib/format'

const columns: Column<Segment>[] = [
  {
    key: 'segment',
    header: 'Segment',
    cell: (s) => (
      <div>
        <p className="font-medium">{s.label}</p>
        <p className="text-muted text-xs">{s.kind === 'theme' ? 'Theme' : 'Category'}</p>
      </div>
    ),
  },
  {
    key: 'baseline',
    header: 'Before',
    align: 'right',
    cell: (s) => `${formatPercent(s.baseline_rate)} (${s.baseline_count})`,
  },
  {
    key: 'candidate',
    header: 'After',
    align: 'right',
    cell: (s) => `${formatPercent(s.candidate_rate)} (${s.candidate_count})`,
  },
  { key: 'ratio', header: 'Change', align: 'right', cell: (s) => formatRatio(s.rate_ratio) },
  { key: 'z', header: 'z', align: 'right', cell: (s) => s.z.toFixed(2) },
  {
    key: 'p',
    header: 'Adjusted p',
    align: 'right',
    cell: (s) => formatPValue(s.adjusted_p_value),
  },
  {
    key: 'flag',
    header: <span className="sr-only">Status</span>,
    cell: (s) => (s.flagged ? <Badge tone="bad">Regression</Badge> : null),
  },
]

function Comparison({ data }: { data: ReleaseComparison }) {
  const { baseline, candidate } = data
  const flagged = data.segments.filter((s) => s.flagged)
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat
          label={`Average rating, ${candidate.version}`}
          value={formatDecimal(candidate.avg_rating)}
          hint={`${formatDecimal(baseline.avg_rating)} in ${baseline.version}`}
        />
        <Stat
          label={`Negative, ${candidate.version}`}
          value={formatPercent(candidate.negative_share)}
          hint={`${formatPercent(baseline.negative_share)} in ${baseline.version}`}
        />
        <Stat
          label="Reviews compared"
          value={`${candidate.reviews} vs ${baseline.reviews}`}
          hint={`${candidate.version} vs ${baseline.version}`}
        />
      </div>

      {flagged.length > 0 && (
        <Card
          title={`${flagged.length} regression${flagged.length === 1 ? '' : 's'} in ${candidate.version}`}
        >
          <ul className="space-y-1">
            {flagged.map((s) => (
              <li key={s.key} className="text-bad font-medium">
                {s.headline}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card
        title="All segments"
        description={`One-sided two-proportion z-test per segment, Holm-adjusted across ${data.segments.length} tests. Flagged when adjusted p < ${data.alpha}, the rate at least ${data.min_ratio}x and at least ${data.min_count} reviews.`}
      >
        <Table
          caption={`Segment rates in ${candidate.version} compared with ${baseline.version}`}
          columns={columns}
          rows={data.segments}
          rowKey={(s) => s.key}
          rowClassName={(s) => (s.flagged ? 'bg-bad-bg/40' : undefined)}
        />
      </Card>
    </div>
  )
}

export function ReleasesPage() {
  const releases = useReleases()
  const [params, setParams] = useSearchParams()
  const candidate = params.get('candidate') ?? undefined
  const comparison = useComparison(candidate)
  const versions = (releases.data ?? [])
    .slice(1)
    .map((r) => ({ value: r.version, label: r.version }))

  return (
    <>
      <PageHeader
        title="Release comparison"
        description="Each release against the one before it. Flags need statistical significance, a real effect size and enough reviews."
        actions={
          <SelectField
            label="Release"
            placeholder="Latest"
            options={[...versions].reverse()}
            value={candidate ?? ''}
            onValueChange={(v) => {
              setParams(v ? { candidate: v } : {})
            }}
          />
        }
      />
      <QueryState query={comparison}>{(data) => <Comparison data={data} />}</QueryState>
    </>
  )
}
