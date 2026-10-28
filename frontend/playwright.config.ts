import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: true,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    channel: process.env.PLAYWRIGHT_CHANNEL,
    ignoreHTTPSErrors: process.env.PLAYWRIGHT_IGNORE_HTTPS_ERRORS === 'true',
    contextOptions: { reducedMotion: 'reduce' },
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? `http://127.0.0.1:${process.env.VITE_PORT ?? 5173}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop-chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 7'] } },
  ],
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : {
    command: 'node ./node_modules/vite/bin/vite.js --host 127.0.0.1',
    url: `http://127.0.0.1:${process.env.VITE_PORT ?? 5173}`,
    reuseExistingServer: !process.env.CI,
  },
})
