import { QueryClient } from '@tanstack/react-query'

import { ApiError } from '../api/client'

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // 4xx responses are answers, not blips; retrying them only delays the error.
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
    },
  })
}
