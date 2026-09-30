import { defineConfig, devices } from '@playwright/test'

// Runs against an already running stack (`docker compose up` or the dev servers).
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:8080'
// Locally we can drive the installed Chrome instead of downloading a browser.
const channel = process.env.PW_CHANNEL

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
    ...(channel ? { channel } : {}),
  },
  projects: [
    { name: 'smoke', testMatch: /smoke\.spec\.ts/ },
    { name: 'screenshots', testMatch: /screenshots\.spec\.ts/ },
  ],
})
