import { NavLink, Outlet } from 'react-router'

import { useHealth } from '../api/hooks'
import { cn } from './ui'
import { ThemeToggle } from './ThemeToggle'

const NAV = [
  { to: '/', label: 'Overview' },
  { to: '/themes', label: 'Themes' },
  { to: '/releases', label: 'Releases' },
  { to: '/reviews', label: 'Reviews' },
  { to: '/replies', label: 'Replies' },
]

export function Layout() {
  const health = useHealth()
  return (
    <div className="min-h-screen">
      <a
        href="#main"
        className="focus:bg-surface sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:rounded focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="border-line bg-surface border-b">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="text-ink flex items-center gap-2 font-semibold">
            <img src="/favicon.svg" alt="" width={22} height={22} />
            Review Radar
          </span>
          <nav aria-label="Main" className="flex flex-wrap gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm',
                    isActive ? 'bg-surface-2 text-ink font-medium' : 'text-ink-2 hover:text-ink',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="text-muted ml-auto flex items-center gap-3 text-xs">
            {health.data && (
              <span>
                Pocket Planner ·{' '}
                {health.data.demo_mode ? (
                  'offline demo model'
                ) : (
                  <>
                    model <span className="text-ink-2 font-medium">{health.data.model}</span>
                  </>
                )}
              </span>
            )}
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
