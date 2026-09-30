import { useId, useState } from 'react'

import { ApiError } from '../api/client'
import { useReplies, useReplyCommand, type ReplyCommand } from '../api/hooks'
import type { Reply, ReplyState, Store } from '../api/types'
import { ReviewSummary } from '../components/ReviewSummary'
import { ReplyStateBadge } from '../components/badges'
import {
  Button,
  Card,
  EmptyState,
  PageHeader,
  Pagination,
  QueryState,
  SelectField,
  cn,
} from '../components/ui'
import { REPLY_STATE_LABELS, STORE_LABELS, formatDate } from '../lib/format'

const PAGE = 10

function readActor() {
  try {
    return localStorage.getItem('actor') ?? ''
  } catch {
    return ''
  }
}

interface ReplyCardProps {
  reply: Reply
  actor: string
  onCommand: (command: ReplyCommand) => void
  busy: boolean
}

export function ReplyCard({ reply, actor, onCommand, busy }: ReplyCardProps) {
  const [text, setText] = useState(reply.body)
  const fieldId = useId()
  const can = (action: Reply['allowed_actions'][number]) => reply.allowed_actions.includes(action)
  const dirty = text.trim() !== reply.body
  const over = text.length > reply.char_limit
  const disabled = busy || !actor
  const editable = can('edit')

  return (
    <Card>
      <ReviewSummary review={reply.review} />
      <div className="border-line mt-4 border-t pt-4">
        <div className="mb-2 flex items-center justify-between gap-2">
          <label htmlFor={fieldId} className="text-ink text-sm font-medium">
            Reply
          </label>
          <div className="text-muted flex items-center gap-2 text-xs">
            <span className={cn('tabular', over && 'text-bad font-medium')}>
              {text.length} / {reply.char_limit}
            </span>
            <ReplyStateBadge state={reply.state} />
          </div>
        </div>
        <textarea
          id={fieldId}
          value={text}
          readOnly={!editable}
          rows={3}
          aria-invalid={over}
          className="border-line bg-surface text-ink read-only:bg-surface-2 w-full rounded-md border p-2 text-sm"
          onChange={(event) => {
            setText(event.target.value)
          }}
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {can('approve') && !dirty && (
            <Button
              variant="primary"
              disabled={disabled}
              onClick={() => {
                onCommand({ kind: 'approve', id: reply.id })
              }}
            >
              Approve
            </Button>
          )}
          {editable && dirty && (
            <Button
              variant="primary"
              disabled={disabled || over}
              onClick={() => {
                onCommand({ kind: 'edit', id: reply.id, body: text.trim() })
              }}
            >
              Approve edit
            </Button>
          )}
          {(can('post') || can('dry_run_post')) && (
            <Button
              variant="primary"
              disabled={disabled || dirty}
              onClick={() => {
                onCommand({ kind: 'post', id: reply.id })
              }}
            >
              Post
            </Button>
          )}
          {can('reject') && (
            <Button
              variant="danger"
              disabled={disabled}
              onClick={() => {
                onCommand({ kind: 'reject', id: reply.id })
              }}
            >
              Reject
            </Button>
          )}
          {can('redraft') && (
            <Button
              disabled={disabled}
              onClick={() => {
                onCommand({ kind: 'redraft', id: reply.id })
              }}
            >
              Reopen
            </Button>
          )}
          {dirty && editable && (
            <Button
              variant="ghost"
              onClick={() => {
                setText(reply.body)
              }}
            >
              Discard changes
            </Button>
          )}
        </div>
        <details className="text-muted mt-3 text-xs">
          <summary className="cursor-pointer">History ({reply.audit.length})</summary>
          <ol className="mt-2 space-y-1">
            {reply.audit.map((entry) => (
              <li key={`${entry.at}-${entry.action}`}>
                {formatDate(entry.at)} · {entry.actor} · {entry.action.replace(/_/g, ' ')} →{' '}
                {REPLY_STATE_LABELS[entry.to_state]}
                {entry.note && ` (${entry.note})`}
              </li>
            ))}
          </ol>
        </details>
      </div>
    </Card>
  )
}

export function RepliesPage() {
  const [state, setState] = useState<ReplyState | ''>('draft')
  const [store, setStore] = useState<Store | ''>('')
  const [offset, setOffset] = useState(0)
  const [actor, setActor] = useState(readActor)
  const replies = useReplies({
    state: state || undefined,
    store: store || undefined,
    limit: PAGE,
    offset,
  })
  const command = useReplyCommand(actor)
  const actorId = useId()

  const error = command.error instanceof ApiError ? command.error.message : null

  return (
    <>
      <PageHeader
        title="Reply approvals"
        description="Drafted replies wait here. Nothing is posted until a named person approves the exact text; every change is logged."
      />
      <Card className="mb-6">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="flex flex-col gap-1">
            <label htmlFor={actorId} className="text-muted text-xs font-medium">
              Reviewing as
            </label>
            <input
              id={actorId}
              value={actor}
              placeholder="Your name"
              maxLength={64}
              className="border-line bg-surface text-ink placeholder:text-muted h-9 rounded-md border px-2 text-sm"
              onChange={(event) => {
                setActor(event.target.value)
                try {
                  localStorage.setItem('actor', event.target.value)
                } catch {
                  // Storage is a convenience here, not a requirement.
                }
              }}
            />
          </div>
          <SelectField
            label="State"
            options={Object.entries(REPLY_STATE_LABELS).map(([value, label]) => ({ value, label }))}
            value={state}
            onValueChange={(v) => {
              setState(v as ReplyState | '')
              setOffset(0)
            }}
          />
          <SelectField
            label="Store"
            options={Object.entries(STORE_LABELS).map(([value, label]) => ({ value, label }))}
            value={store}
            onValueChange={(v) => {
              setStore(v as Store | '')
              setOffset(0)
            }}
          />
        </div>
        {!actor && (
          <p className="text-warn mt-3 text-sm">
            Enter your name to approve, edit or post replies.
          </p>
        )}
        {error && (
          <p role="alert" className="text-bad mt-3 text-sm">
            {error}
          </p>
        )}
      </Card>

      <QueryState query={replies}>
        {(page) =>
          page.items.length === 0 ? (
            <EmptyState title="Nothing in this queue" />
          ) : (
            <div className="space-y-4">
              <p className="text-muted text-sm">{page.total} replies, most severe first</p>
              {page.items.map((reply) => (
                <ReplyCard
                  key={`${reply.id}-${reply.updated_at}`}
                  reply={reply}
                  actor={actor}
                  busy={command.isPending}
                  onCommand={(c) => {
                    command.mutate(c)
                  }}
                />
              ))}
              <Pagination
                total={page.total}
                limit={page.limit}
                offset={page.offset}
                onChange={setOffset}
              />
            </div>
          )
        }
      </QueryState>
    </>
  )
}
