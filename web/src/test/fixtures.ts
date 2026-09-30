import type { Reply, Review } from '../api/types'

export const review: Review = {
  id: 'rev-1',
  store: 'google_play',
  external_id: 'gp-1',
  rating: 1,
  title: null,
  body: 'Crashes every time I log in.',
  language: 'en',
  app_version: '2.3.0',
  territory: 'US',
  author: 'QuietOtter7',
  created_at: '2026-05-06T10:00:00Z',
  triage: {
    sentiment: 'negative',
    category: 'crash',
    severity: 'critical',
    summary: 'App crashes when signing in',
    language: 'en',
    model_name: 'demo-rules',
  },
  theme_id: null,
  theme_title: null,
  reply_state: 'draft',
}

export const reply: Reply = {
  id: 'reply-1',
  state: 'draft',
  body: 'Sorry about the crash.',
  drafted_body: 'Sorry about the crash.',
  char_limit: 40,
  model_name: 'demo-rules',
  approved_by: null,
  approved_at: null,
  posted_at: null,
  updated_at: '2026-09-01T09:00:00Z',
  allowed_actions: ['approve', 'edit', 'reject'],
  review,
  audit: [
    {
      action: 'draft',
      from_state: null,
      to_state: 'draft',
      actor: 'agent:demo-rules',
      note: null,
      at: '2026-09-01T09:00:00Z',
    },
  ],
}
