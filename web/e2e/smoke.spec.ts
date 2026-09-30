import { expect, test } from '@playwright/test'

test('overview shows KPIs and the seeded 2.3.0 regression', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
  await expect(page.getByText('Average rating', { exact: true })).toBeVisible()
  await expect(page.getByText(/App crashes when signing in up .* in 2\.3\.0/)).toBeVisible()
})

test('release comparison flags 2.3.0 and clears 2.3.1', async ({ page }) => {
  await page.goto('/releases?candidate=2.3.0')
  await expect(page.getByText(/regressions? in 2\.3\.0/)).toBeVisible()
  await page.goto('/releases?candidate=2.3.1')
  await expect(page.getByRole('table')).toBeVisible()
  await expect(page.getByText(/regressions? in 2\.3\.1/)).toHaveCount(0)
})

test('review explorer filters by category', async ({ page }) => {
  await page.goto('/reviews')
  await page.getByLabel('Category').selectOption('crash')
  await expect(page).toHaveURL(/category=crash/)
  await expect(page.getByRole('heading', { name: /\d+ reviews/ })).toBeVisible()
})

test('reply queue needs a name before approving', async ({ page }) => {
  await page.goto('/replies')
  const approve = page.getByRole('button', { name: 'Approve', exact: true }).first()
  await expect(approve).toBeDisabled()
  await page.getByLabel('Reviewing as').fill('Smoke Test')
  await expect(approve).toBeEnabled()
})
