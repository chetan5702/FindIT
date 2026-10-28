import { expect, test, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { readIdentityToken } from './mail-helper'

async function register(page: Page, email: string) {
  await page.goto('/register', { waitUntil: 'domcontentloaded' })
  await page.locator('#full_name').fill('Recovery Tester')
  await page.locator('#register-email').fill(email)
  await page.locator('#register-password').fill('BrowserTest12345!')
  await page.locator('#confirm').fill('BrowserTest12345!')
  await page.getByRole('checkbox').check()
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  if (process.env.FINDIT_REQUIRE_EMAIL_VERIFICATION === 'true') {
    await expect(page.getByRole('heading', { name: 'Check your institutional email' })).toBeVisible()
    const token = await readIdentityToken(email, 'verify-email')
    await page.goto(`/verify-email#token=${token}`, { waitUntil: 'domcontentloaded' })
    await page.locator('#new-password').fill('BrowserTest12345!')
    await page.locator('#confirm-password').fill('BrowserTest12345!')
    await page.getByRole('button', { name: 'Confirm email verification', exact: true }).click()
    await expect(page.getByRole('status')).toContainText('Email verified')
    await page.goto('/login', { waitUntil: 'domcontentloaded' })
    await page.locator('#email').fill(email)
    await page.locator('#password').fill('BrowserTest12345!')
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  }
  await expect(page).toHaveURL(/\/app$/)
}

async function report(page: Page, type: 'lost' | 'found', name: string) {
  await page.goto(`/app/report/${type}`, { waitUntil: 'domcontentloaded' })
  await page.locator('#item_name').fill(name)
  await page.locator('#category_id').selectOption({ label: 'Electronics' })
  await page.locator('#description').fill('Blue wireless headphones inside a black protective case.')
  await page.locator('#approximate_location').fill('Library study area')
  // Use a known past time to avoid minute-boundary/future validation races.
  await page.locator('#occurred_at').fill('2026-01-01T12:00')
  await page.locator('#private_details').fill('Secret serial suffix 1934')
  await page.getByRole('button', { name: `Submit ${type} report`, exact: true }).click()
  await expect(page).toHaveURL(/\/app\/reports\/[0-9a-f-]+$/)
  return page.url().split('/').at(-1)!
}

test('students report and claim an item; staff record custody and handover', async ({ browser, baseURL }, testInfo) => {
  test.skip(!process.env.FINDIT_E2E_STAFF_EMAIL || !process.env.FINDIT_E2E_STAFF_PASSWORD,
    'Requires a disposable database initialized with python -m app.e2e_fixture')
  test.setTimeout(120_000)
  const { viewport, isMobile, hasTouch, deviceScaleFactor, userAgent } = testInfo.project.use
  const contexts = await Promise.all([0, 1, 2].map(() => browser.newContext({ baseURL, viewport, isMobile, hasTouch, deviceScaleFactor, userAgent, reducedMotion: 'reduce', ignoreHTTPSErrors: process.env.PLAYWRIGHT_IGNORE_HTTPS_ERRORS === 'true' })))
  try {
    contexts.forEach(context => context.setDefaultTimeout(15_000))
    await Promise.all(contexts.map(context => context.route(/https:\/\/fonts\.(googleapis|gstatic)\.com\//, route => route.abort())))
    const [finder, owner, staff] = await Promise.all(contexts.map(context => context.newPage()))
    const suffix = randomUUID()
    await register(finder, `finder-${suffix}@suh.edu.in`)
    const foundId = await report(finder, 'found', `Recovery headphones ${suffix}`)
    await register(owner, `owner-${suffix}@suh.edu.in`)
    const lostId = await report(owner, 'lost', `Lost headphones ${suffix}`)
    // Refresh CSRF while signed in, then exercise the next UI mutation.
    expect((await owner.request.get('/api/v1/auth/csrf')).ok()).toBeTruthy()
    await owner.goto(`/app/reports/${foundId}`)
    await expect(owner.getByText('Secret serial suffix 1934', { exact: true })).toHaveCount(0)
    await owner.getByRole('link', { name: 'This might be mine' }).click()
    await owner.locator('#lost_report_id').selectOption(lostId)
    await owner.getByLabel('Private ownership proof', { exact: false }).fill('The serial number ends with 1934 and I left the case in the library.')
    await owner.getByRole('button', { name: 'Submit private claim', exact: true }).click()
    await expect(owner).toHaveURL(/\/app\/claims\/[0-9a-f-]+$/)
    const claimId = owner.url().split('/').at(-1)!
    // The finder cannot view somebody else's private claim.
    expect((await finder.request.get(`/api/v1/claims/${claimId}`)).status()).toBe(403)
    await staff.goto('/login')
    await staff.getByLabel('Campus email', { exact: false }).fill(process.env.FINDIT_E2E_STAFF_EMAIL!)
    await staff.locator('#password').fill(process.env.FINDIT_E2E_STAFF_PASSWORD!)
    await staff.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(staff).toHaveURL(/\/staff$/)
    await staff.goto(`/staff/custody?report=${foundId}`)
    await staff.getByLabel('Secure storage location', { exact: false }).fill('E2E security locker')
    const custodyConfirm = staff.getByRole('dialog').getByRole('button', { name: 'Record custody', exact: true })
    await staff.locator('#storage_location').blur()
    await expect.poll(() => custodyConfirm.evaluate(button => {
      const rect = button.getBoundingClientRect()
      const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)
      return !!hit && (hit === button || button.contains(hit))
    })).toBe(true)
    if (hasTouch) {
      // Use the verified viewport point for the native touch gesture. This avoids
      // an extra scroll-into-view moving a fixed dialog after mobile input focus.
      const point = await custodyConfirm.evaluate(button => {
        const rect = button.getBoundingClientRect()
        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
      })
      await staff.touchscreen.tap(point.x, point.y)
    } else await custodyConfirm.click()
    await expect(staff.getByRole('dialog')).toHaveCount(0)
    await staff.goto(`/staff/claims/${claimId}`)
    await staff.getByRole('button', { name: 'Start review', exact: true }).click()
    await staff.getByRole('dialog').getByRole('button', { name: 'Start review', exact: true }).click()
    await expect(staff.getByRole('dialog')).toHaveCount(0)
    await staff.getByRole('button', { name: 'Approve ownership', exact: true }).click()
    await staff.getByRole('dialog').getByRole('button', { name: 'Approve claim', exact: true }).click()
    await expect(staff.getByRole('button', { name: 'Record handover', exact: true })).toBeVisible()
    await staff.getByRole('button', { name: 'Record handover', exact: true }).click()
    await staff.getByRole('dialog').getByRole('button', { name: 'Confirm handover', exact: true }).click()
    await expect(staff.getByText('This handover is complete and cannot be reopened through ordinary controls.')).toBeVisible()
    await owner.reload()
    await expect(owner.getByText('Handover complete', { exact: true })).toBeVisible()
    expect((await owner.request.get(`/api/v1/reports/${lostId}`)).ok()).toBeTruthy()
    expect((await (await finder.request.get(`/api/v1/reports/${foundId}`)).json()).status).toBe('returned')
  } finally {
    for (const context of contexts) {
      for (const page of context.pages()) await page.close()
      await context.close()
    }
  }
})
