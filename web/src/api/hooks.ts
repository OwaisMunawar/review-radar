import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from './client'
import type {
  Health,
  Overview,
  Release,
  ReleaseComparison,
  Reply,
  ReplyPage,
  ReplyQuery,
  ReviewPage,
  ReviewQuery,
  Segment,
  Theme,
} from './types'

export const keys = {
  health: ['health'] as const,
  overview: ['overview'] as const,
  themes: ['themes'] as const,
  releases: ['releases'] as const,
  comparison: (candidate?: string, baseline?: string) =>
    ['releases', 'compare', candidate ?? 'latest', baseline ?? 'previous'] as const,
  regressions: ['releases', 'regressions'] as const,
  reviews: (query: ReviewQuery) => ['reviews', query] as const,
  replies: (query: ReplyQuery) => ['replies', query] as const,
}

export const useHealth = () =>
  useQuery({ queryKey: keys.health, queryFn: () => api.get<Health>('/health') })

export const useOverview = () =>
  useQuery({ queryKey: keys.overview, queryFn: () => api.get<Overview>('/overview') })

export const useThemes = () =>
  useQuery({ queryKey: keys.themes, queryFn: () => api.get<Theme[]>('/themes') })

export const useReleases = () =>
  useQuery({ queryKey: keys.releases, queryFn: () => api.get<Release[]>('/releases') })

export const useRegressions = () =>
  useQuery({
    queryKey: keys.regressions,
    queryFn: () => api.get<Segment[]>('/releases/regressions'),
  })

export const useComparison = (candidate?: string, baseline?: string) =>
  useQuery({
    queryKey: keys.comparison(candidate, baseline),
    queryFn: () => api.get<ReleaseComparison>('/releases/compare', { candidate, baseline }),
    placeholderData: keepPreviousData,
  })

export const useReviews = (query: ReviewQuery) =>
  useQuery({
    queryKey: keys.reviews(query),
    queryFn: () => api.get<ReviewPage>('/reviews', { ...query }),
    placeholderData: keepPreviousData,
  })

export const useReplies = (query: ReplyQuery) =>
  useQuery({
    queryKey: keys.replies(query),
    queryFn: () => api.get<ReplyPage>('/replies', { ...query }),
    placeholderData: keepPreviousData,
  })

export type ReplyCommand =
  | { kind: 'approve'; id: string }
  | { kind: 'reject'; id: string; note?: string }
  | { kind: 'edit'; id: string; body: string }
  | { kind: 'post'; id: string }
  | { kind: 'redraft'; id: string }

export function useReplyCommand(actor: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (command: ReplyCommand) => {
      const { kind, id, ...rest } = command
      return api.post<Reply>(`/replies/${id}/${kind}`, { actor, ...rest })
    },
    onSuccess: () => {
      // The queue and the overview's pending count both depend on reply state.
      void client.invalidateQueries({ queryKey: ['replies'] })
      void client.invalidateQueries({ queryKey: keys.overview })
    },
  })
}
