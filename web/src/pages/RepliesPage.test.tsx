import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'

import { reply } from '../test/fixtures'
import { ReplyCard, RepliesPage } from './RepliesPage'

function wrap(children: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('ReplyCard', () => {
  it('approves the drafted text as is', async () => {
    const onCommand = vi.fn()
    render(<ReplyCard reply={reply} actor="dana" busy={false} onCommand={onCommand} />)
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(onCommand).toHaveBeenCalledWith({ kind: 'approve', id: 'reply-1' })
  })

  it('turns approve into "approve edit" once the text changes', async () => {
    const onCommand = vi.fn()
    render(<ReplyCard reply={reply} actor="dana" busy={false} onCommand={onCommand} />)
    const box = screen.getByRole('textbox', { name: 'Reply' })
    await userEvent.clear(box)
    await userEvent.type(box, 'Fixed in 2.3.1')
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Approve edit' }))
    expect(onCommand).toHaveBeenCalledWith({ kind: 'edit', id: 'reply-1', body: 'Fixed in 2.3.1' })
  })

  it('blocks text over the store limit', async () => {
    render(<ReplyCard reply={reply} actor="dana" busy={false} onCommand={vi.fn()} />)
    const box = screen.getByRole('textbox', { name: 'Reply' })
    await userEvent.type(box, ' and this makes it far too long')
    expect(box).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('button', { name: 'Approve edit' })).toBeDisabled()
  })

  it('needs a reviewer name before any action', () => {
    render(<ReplyCard reply={reply} actor="" busy={false} onCommand={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled()
  })

  it('offers post only once approved', () => {
    const approved = {
      ...reply,
      state: 'approved' as const,
      allowed_actions: ['edit', 'reject', 'post'] as const,
    }
    render(
      <ReplyCard
        reply={{ ...approved, allowed_actions: [...approved.allowed_actions] }}
        actor="dana"
        busy={false}
        onCommand={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: 'Post' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument()
  })
})

describe('RepliesPage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('loads the draft queue and sends the reviewer name with an approval', async () => {
    localStorage.setItem('actor', 'dana')
    const calls: { url: string; init?: RequestInit }[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init?: RequestInit) => {
        calls.push({ url, ...(init ? { init } : {}) })
        const body = url.startsWith('/api/replies?')
          ? { items: [reply], total: 1, limit: 10, offset: 0 }
          : { ...reply, state: 'approved' }
        return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))
      }),
    )

    render(wrap(<RepliesPage />))
    expect(await screen.findByText('Crashes every time I log in.')).toBeInTheDocument()
    expect(calls[0]?.url).toBe('/api/replies?state=draft&limit=10&offset=0')

    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    await waitFor(() => {
      expect(calls.some((c) => c.url === '/api/replies/reply-1/approve')).toBe(true)
    })
    const post = calls.find((c) => c.url === '/api/replies/reply-1/approve')
    expect(post?.init?.body).toBe(JSON.stringify({ actor: 'dana' }))
  })

  it('surfaces API errors from a rejected command', async () => {
    localStorage.setItem('actor', 'dana')
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url.startsWith('/api/replies?')) {
          return Promise.resolve(
            new Response(JSON.stringify({ items: [reply], total: 1, limit: 10, offset: 0 })),
          )
        }
        const error = {
          error: {
            code: 'invalid_transition',
            message: 'cannot post a reply that is draft',
            details: {},
          },
        }
        return Promise.resolve(new Response(JSON.stringify(error), { status: 409 }))
      }),
    )
    render(wrap(<RepliesPage />))
    await userEvent.click(await screen.findByRole('button', { name: 'Reject' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('cannot post a reply that is draft')
  })
})
