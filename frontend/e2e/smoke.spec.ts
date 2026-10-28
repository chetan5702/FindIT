import { expect, test } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\//, route => route.abort())
})

test('landing page exposes the two primary recovery journeys', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: /lost something/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /report a lost item/i })).toBeVisible()
  await expect(page.getByRole('link', { name: /report a found item/i })).toBeVisible()
})

test('login form is keyboard accessible', async ({ page }) => {
  await page.goto('/login', { waitUntil: 'domcontentloaded' })
  await page.getByLabel(/campus email/i).fill('student@example.edu')
  await page.getByLabel(/^password/i).fill('not-a-real-password')
  await expect(page.getByRole('button', { name: /sign in/i })).toBeEnabled()
})
