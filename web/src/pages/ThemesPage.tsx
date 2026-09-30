import { Link } from 'react-router'

import { useThemes } from '../api/hooks'
import type { Theme } from '../api/types'
import { CategoryBadge } from '../components/badges'
import { ReviewSummary } from '../components/ReviewSummary'
import { Badge, Card, EmptyState, PageHeader, QueryState, Sparkline } from '../components/ui'
import { formatPercent } from '../lib/format'

const TREND = {
  rising: { tone: 'bad', label: 'Rising' },
  falling: { tone: 'good', label: 'Falling' },
  stable: { tone: 'neutral', label: 'Stable' },
} as const

function ThemeCard({ theme }: { theme: Theme }) {
  const trend = TREND[theme.trend]
  const sample = theme.representatives[0]
  return (
    <Card
      title={theme.title}
      description={`${theme.size} reviews · ${formatPercent(theme.negative_share)} negative`}
      actions={<Badge tone={trend.tone}>{trend.label}</Badge>}
    >
      <div className="flex items-end justify-between gap-4">
        <CategoryBadge category={theme.dominant_category} />
        <Sparkline values={theme.weekly_counts} label={`${theme.title}, reviews per week`} />
      </div>
      {sample && (
        <div className="border-line mt-4 border-t pt-4">
          <ReviewSummary review={sample} />
        </div>
      )}
      <Link
        to={`/reviews?theme_id=${theme.id}`}
        className="text-accent mt-4 inline-block text-sm hover:underline"
      >
        All {theme.size} reviews
      </Link>
    </Card>
  )
}

/** Problems first: negative reviews in a theme are what someone has to act on. */
const byImpact = (themes: Theme[]) =>
  [...themes].sort(
    (a, b) => b.size * b.negative_share - a.size * a.negative_share || b.size - a.size,
  )

export function ThemesPage() {
  const themes = useThemes()
  return (
    <>
      <PageHeader
        title="Themes"
        description="Reviews grouped by what they say, across languages, with the most negative volume first. Sparklines show the last 12 weeks."
      />
      <QueryState query={themes}>
        {(data) =>
          data.length === 0 ? (
            <EmptyState title="No themes yet">
              Run the pipeline to cluster triaged reviews.
            </EmptyState>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {byImpact(data).map((theme) => (
                <ThemeCard key={theme.id} theme={theme} />
              ))}
            </div>
          )
        }
      </QueryState>
    </>
  )
}
