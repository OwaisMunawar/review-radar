import type { ApiErrorBody } from './types'

/** An error response from the API, carrying the server's stable error code. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, body: ApiErrorBody | null) {
    super(body?.error.message ?? `request failed with ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.code = body?.error.code ?? 'http_error'
    this.details = body?.error.details ?? {}
  }
}

type Query = Record<string, string | number | undefined>

function withQuery(path: string, query?: Query): string {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown, query?: Query) {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const init: RequestInit = { method, headers }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }
  const response = await fetch(withQuery(`/api${path}`, query), init)
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as ApiErrorBody | null
    throw new ApiError(response.status, payload)
  }
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, undefined, query),
  post: <T>(path: string, body: unknown) => request<T>('POST', path, body),
}
