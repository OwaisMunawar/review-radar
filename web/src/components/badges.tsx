import type { Category, ReplyState, Sentiment, Severity } from '../api/types'
import {
  CATEGORY_LABELS,
  REPLY_STATE_LABELS,
  SENTIMENT_LABELS,
  SEVERITY_LABELS,
} from '../lib/format'
import { Badge, type Tone } from './ui'

const SENTIMENT_TONE: Record<Sentiment, Tone> = {
  positive: 'good',
  neutral: 'neutral',
  negative: 'bad',
}

const SEVERITY_TONE: Record<Severity, Tone> = {
  critical: 'bad',
  high: 'warn',
  medium: 'neutral',
  low: 'neutral',
}

const STATE_TONE: Record<ReplyState, Tone> = {
  draft: 'info',
  approved: 'good',
  edited: 'good',
  rejected: 'neutral',
  posted: 'good',
  would_post: 'warn',
}

export const CategoryBadge = ({ category }: { category: Category }) => (
  <Badge>{CATEGORY_LABELS[category]}</Badge>
)

export const SentimentBadge = ({ sentiment }: { sentiment: Sentiment }) => (
  <Badge tone={SENTIMENT_TONE[sentiment]}>{SENTIMENT_LABELS[sentiment]}</Badge>
)

export const SeverityBadge = ({ severity }: { severity: Severity }) => (
  <Badge tone={SEVERITY_TONE[severity]}>{SEVERITY_LABELS[severity]}</Badge>
)

export const ReplyStateBadge = ({ state }: { state: ReplyState }) => (
  <Badge tone={STATE_TONE[state]}>{REPLY_STATE_LABELS[state]}</Badge>
)
