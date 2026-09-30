import type { Category, ReplyState, Sentiment, Severity, Store } from '../api/types'

export const CATEGORY_LABELS: Record<Category, string> = {
  crash: 'Crash',
  performance: 'Performance',
  login: 'Login / auth',
  payments: 'Payments / billing',
  ux: 'UX',
  feature_request: 'Feature request',
  praise: 'Praise',
  other: 'Other',
}

export const STORE_LABELS: Record<Store, string> = {
  app_store: 'App Store',
  google_play: 'Google Play',
}

export const SENTIMENT_LABELS: Record<Sentiment, string> = {
  positive: 'Positive',
  neutral: 'Neutral',
  negative: 'Negative',
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: 'Critical',
  high: 'High',
  medium: 'Medium',
  low: 'Low',
}

export const REPLY_STATE_LABELS: Record<ReplyState, string> = {
  draft: 'Draft',
  approved: 'Approved',
  edited: 'Edited',
  rejected: 'Rejected',
  posted: 'Posted',
  would_post: 'Would post',
}

const percent = new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 1 })
const decimal = new Intl.NumberFormat('en', { maximumFractionDigits: 2 })
const integer = new Intl.NumberFormat('en')
const day = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric', year: 'numeric' })
const shortDay = new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' })

export const formatPercent = (value: number | null | undefined) =>
  value === null || value === undefined ? '–' : percent.format(value)
export const formatDecimal = (value: number | null | undefined) =>
  value === null || value === undefined ? '–' : decimal.format(value)
export const formatInt = (value: number) => integer.format(value)
export const formatDate = (iso: string) => day.format(new Date(iso))
export const formatShortDate = (iso: string) => shortDay.format(new Date(iso))

export function formatRatio(ratio: number | null) {
  return ratio === null ? 'new' : `${ratio.toFixed(1)}x`
}

export function formatPValue(p: number) {
  if (p < 0.0001) return '< 0.0001'
  return p.toFixed(4)
}
