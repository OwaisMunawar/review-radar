import { useState } from 'react'

type Mode = 'system' | 'light' | 'dark'

function read(): Mode {
  try {
    const saved = localStorage.getItem('theme')
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  } catch {
    return 'system'
  }
}

function apply(mode: Mode) {
  const root = document.documentElement
  if (mode === 'system') delete root.dataset.theme
  else root.dataset.theme = mode
  try {
    if (mode === 'system') localStorage.removeItem('theme')
    else localStorage.setItem('theme', mode)
  } catch {
    // Private windows can refuse storage; the choice still applies for this visit.
  }
}

const NEXT: Record<Mode, Mode> = { system: 'light', light: 'dark', dark: 'system' }
const LABEL: Record<Mode, string> = {
  system: 'System theme',
  light: 'Light theme',
  dark: 'Dark theme',
}

export function ThemeToggle() {
  const [mode, setMode] = useState<Mode>(read)
  return (
    <button
      type="button"
      className="text-ink-2 hover:bg-surface-2 hover:text-ink rounded-md px-2 py-1 text-sm"
      aria-label={`${LABEL[mode]}. Switch to ${LABEL[NEXT[mode]].toLowerCase()}`}
      onClick={() => {
        const next = NEXT[mode]
        apply(next)
        setMode(next)
      }}
    >
      {LABEL[mode]}
    </button>
  )
}
