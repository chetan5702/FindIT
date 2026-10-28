const API_BASE = `${(import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')}/api/v1`

export interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: unknown; request_id?: string }
  detail?: string | { msg?: string }[]
}

export class ApiError extends Error {
  status: number
  code?: string
  details?: unknown
  requestId?: string

  constructor(status: number, body: ApiErrorBody = {}) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).filter(Boolean).join(', ')
      : body.detail
    super(body.error?.message || detail || `Request failed (${status})`)
    this.name = 'ApiError'
    this.status = status
    this.code = body.error?.code
    this.details = body.error?.details
    this.requestId = body.error?.request_id
  }
}

let csrfToken: string | null = null

function cookie(name: string) {
  if (typeof document === 'undefined') return null
  const entry = document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))
  return entry ? decodeURIComponent(entry.slice(name.length + 1)) : null
}

async function ensureCsrf() {
  // Always prefer the current cookie; the server rotates it after authentication.
  const currentCookieToken = cookie('findit_csrf')
  if (currentCookieToken) {
    csrfToken = currentCookieToken
    return currentCookieToken
  }
  // A cached pre-login token must never override a deleted/rotated cookie.
  csrfToken = null
  const response = await fetch(`${API_BASE}/auth/csrf`, { credentials: 'include' })
  if (!response.ok) throw new ApiError(response.status, await safeJson(response))
  const data = await response.json() as { csrf_token: string }
  csrfToken = data.csrf_token
  return csrfToken
}

async function safeJson(response: Response): Promise<ApiErrorBody> {
  try { return await response.json() as ApiErrorBody } catch { return {} }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  formData?: FormData
  skipCsrf?: boolean
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? 'GET').toUpperCase()
  const mutating = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  const headers = new Headers(options.headers)
  if (mutating && !options.skipCsrf) headers.set('X-CSRF-Token', await ensureCsrf())
  let body: BodyInit | undefined
  if (options.formData) body = options.formData
  else if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
    body = JSON.stringify(options.body)
  }
  const response = await fetch(`${API_BASE}${path}`, { ...options, method, headers, body, credentials: 'include' })
  if (!response.ok) throw new ApiError(response.status, await safeJson(response))
  if (response.status === 204) return undefined as T
  const contentType = response.headers.get('content-type') ?? ''
  return contentType.includes('application/json') ? response.json() as Promise<T> : response.blob() as Promise<T>
}

export function imageUrl(reportId: string, image: { id: string; url?: string }) {
  if (image.url) return image.url.startsWith('http') ? image.url : `${import.meta.env.VITE_API_URL ?? ''}${image.url}`
  return `${API_BASE}/reports/${reportId}/images/${image.id}`
}

export function queryString(values: Record<string, string | number | boolean | null | undefined>) {
  const params = new URLSearchParams()
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  })
  const text = params.toString()
  return text ? `?${text}` : ''
}

export function resetCsrf() { csrfToken = null }
