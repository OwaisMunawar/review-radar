import type { ReactNode } from 'react'

import { cn } from './cn'

export type Tone = 'neutral' | 'info' | 'good' | 'warn' | 'bad'

const TONES: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-ink-2',
  info: 'bg-info-bg text-accent',
  good: 'bg-good-bg text-good',
  warn: 'bg-warn-bg text-warn',
  bad: 'bg-bad-bg text-bad',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap',
        TONES[tone],
      )}
    >
      {children}
    </span>
  )
}
