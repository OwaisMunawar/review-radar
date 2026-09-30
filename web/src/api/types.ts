import type { components } from './schema'

type Schemas = components['schemas']

export type Overview = Schemas['OverviewView']
export type Review = Schemas['ReviewView']
export type ReviewPage = Schemas['Page_ReviewView_']
export type Theme = Schemas['ThemeView']
export type Release = Schemas['ReleaseSummaryView']
export type ReleaseComparison = Schemas['ReleaseComparisonView']
export type Segment = Schemas['SegmentComparisonView']
export type Reply = Schemas['ReplyView']
export type ReplyPage = Schemas['Page_ReplyView_']
export type ReplyState = Schemas['ReplyState']
export type ReplyAction = Schemas['ReplyAction']
export type Category = Schemas['Category']
export type Sentiment = Schemas['Sentiment']
export type Severity = Schemas['Severity']
export type Store = Schemas['Store']
export type Health = Schemas['Health']
export type ApiErrorBody = Schemas['ErrorResponse']

export interface ReviewQuery {
  store?: Store | undefined
  category?: Category | undefined
  sentiment?: Sentiment | undefined
  severity?: Severity | undefined
  version?: string | undefined
  theme_id?: string | undefined
  q?: string | undefined
  limit?: number
  offset?: number
}

export interface ReplyQuery {
  state?: ReplyState | undefined
  store?: Store | undefined
  limit?: number
  offset?: number
}
