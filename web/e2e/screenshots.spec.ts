import { test } from '@playwright/test'

// Real captures of the running dashboard for the README: `npm run screenshots`.
const OUT = '../docs/screenshots'
const PAGES = [
  { name: 'overview', path: '/' },
  { name: 'releases', path: '/releases?candidate=2.3.0' },
  { name: 'themes', path: '/themes' },
  { name: 'replies', path: '/replies' },
  { name: 'reviews', path: '/reviews?version=2.3.0&category=crash' },
]

test.use({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 2 })

for (const scheme of ['light', 'dark'] as const) {
  test.describe(scheme, () => {
    test.use({ colorScheme: scheme })
    for (const { name, path } of PAGES) {
      test(name, async ({ page }) => {
        await page.goto(path)
        await page.waitForLoadState('networkidle')
        await page.getByRole('status', { name: 'Loading' }).first().waitFor({ state: 'detached' })
        await page.screenshot({ path: `${OUT}/${name}-${scheme}.png` })
      })
    }
  })
}
