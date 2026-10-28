import { beforeEach, describe, expect, it, vi } from 'vitest'
import { authApi, reportsApi } from '../lib/endpoints'
import { resetCsrf } from '../lib/api'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

beforeEach(() => {
  document.cookie = 'findit_csrf=; Max-Age=0; path=/'
  resetCsrf()
})

describe('API request security and routing', () => {
  it('uses the rotated session CSRF cookie for the first report after registration', async () => {
    document.cookie = 'findit_csrf=guest-token; path=/'
    const fetchMock = vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const address = String(input)
      if (address.endsWith('/auth/register')) {
        expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe('guest-token')
        document.cookie = 'findit_csrf=session-token; path=/'
        return jsonResponse({ user: { id: 'u1', role: 'student' } }, 201)
      }
      if (address.endsWith('/reports')) {
        expect(new Headers(options?.headers).get('X-CSRF-Token')).toBe('session-token')
        return jsonResponse({ id: 'r1' }, 201)
      }
      throw new Error(`Unexpected request to ${address}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    await authApi.register({ email: 'student@example.com', password: 'Password123456', full_name: 'Student' })
    await reportsApi.create({ item_name: 'Blue backpack' })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('queries the privacy-restricted guest catalog from public browsing', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _options?: RequestInit) => jsonResponse({ items: [], total: 0, page: 1, page_size: 12, pages: 0 }))
    vi.stubGlobal('fetch', fetchMock)
    await reportsApi.publicList({ report_type: 'found', page: 1 })
    expect(String(fetchMock.mock.calls[0][0])).toContain('/reports/public?report_type=found&page=1')
  })

  it('includes cookies on authenticated requests', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _options?: RequestInit) => jsonResponse({ items: [], total: 0, page: 1, page_size: 12, pages: 0 }))
    vi.stubGlobal('fetch', fetchMock)
    await reportsApi.list()
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: 'include' })
  })
})
