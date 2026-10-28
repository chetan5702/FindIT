import { api, queryString } from './api'
import type { AdminDashboardData, AuditEvent, Category, Claim, CustodyRecord, Handover, Location, MatchResult, Notification, Page, Report, StaffDashboardData, User } from '../types/api'

export interface AuthResult { user: User | null; verification_required: boolean; message?: string }
export interface AuthSessionInfo { id: string; created_at: string; expires_at: string; user_agent?: string; current: boolean }
export const authApi = {
  requestVerification: (email: string) => api<{ message: string }>('/auth/verification/request', { method: 'POST', body: { email } }),
  verifyEmail: (token: string, password: string) => api<{ message: string }>('/auth/verification/confirm', { method: 'POST', body: { token, password } }),
  forgotPassword: (email: string) => api<{ message: string }>('/auth/password/forgot', { method: 'POST', body: { email } }),
  resetPassword: (token: string, password: string) => api<{ message: string }>('/auth/password/reset', { method: 'POST', body: { token, password } }),
  changePassword: (current_password: string, password: string) => api<{ message: string }>('/auth/password/change', { method: 'POST', body: { current_password, password } }),
  sessions: () => api<AuthSessionInfo[]>('/auth/sessions'),
  revokeSession: (id: string) => api<void>(`/auth/sessions/${id}`, { method: 'DELETE' }),
  logoutAll: () => api<void>('/auth/logout-all', { method: 'POST' }),
  csrf: () => api<{ csrf_token: string }>('/auth/csrf'),
  me: () => api<User>('/auth/me'),
  login: (input: { email: string; password: string }) => api<AuthResult>('/auth/login', { method: 'POST', body: input }),
  register: (input: { full_name: string; email: string; password: string }) => api<AuthResult>('/auth/register', { method: 'POST', body: input }),
  logout: () => api<void>('/auth/logout', { method: 'POST' }),
  updateProfile: (input: { full_name: string }) => api<User | { user: User }>('/profile', { method: 'PATCH', body: input }),
}

export const catalogApi = {
  categories: () => api<Category[]>('/categories'),
  locations: () => api<Location[]>('/locations'),
}

export type ReportFilters = { report_type?: string; category_id?: string; location_id?: string; status?: string; q?: string; date_from?: string; date_to?: string; page?: number; page_size?: number; mine?: boolean }
export const reportsApi = {
  list: (filters: ReportFilters = {}) => api<Page<Report>>(`/reports${queryString(filters)}`),
  publicList: (filters: ReportFilters = {}) => api<Page<Report>>(`/reports/public${queryString(filters)}`),
  get: (id: string) => api<Report>(`/reports/${id}`),
  create: (input: object) => api<Report>('/reports', { method: 'POST', body: input }),
  update: (id: string, input: object) => api<Report>(`/reports/${id}`, { method: 'PATCH', body: input }),
  remove: (id: string) => api<void>(`/reports/${id}`, { method: 'DELETE' }),
  uploadImage: (id: string, file: File) => { const formData = new FormData(); formData.append('file', file); return api(`/reports/${id}/images`, { method: 'POST', formData }) },
  deleteImage: (id: string, imageId: string) => api<void>(`/reports/${id}/images/${imageId}`, { method: 'DELETE' }),
  matches: (id: string, page = 1) => api<Page<MatchResult>>(`/reports/${id}/matches${queryString({ page, page_size: 50 })}`),
}

export const claimsApi = {
  list: (filters: Record<string, string | number | undefined> = {}) => api<Page<Claim>>(`/claims${queryString(filters)}`),
  get: (id: string) => api<Claim>(`/claims/${id}`),
  create: (foundId: string, input: { proof_text: string; lost_report_id?: string }) => api<Claim>(`/reports/${foundId}/claims`, { method: 'POST', body: input }),
  uploadEvidence: (id: string, file: File) => { const formData = new FormData(); formData.append('file', file); return api(`/claims/${id}/evidence`, { method: 'POST', formData }) },
}

export const notificationsApi = {
  list: (page = 1) => api<Page<Notification>>(`/notifications${queryString({ page, page_size: 30 })}`),
  read: (id: string) => api<void>(`/notifications/${id}/read`, { method: 'POST' }),
  readAll: () => api<void>('/notifications/read-all', { method: 'POST' }),
}

export const staffApi = {
  dashboard: () => api<StaffDashboardData>('/staff/dashboard'),
  claims: (filters: Record<string, string | number | undefined> = {}) => api<Page<Claim>>(`/claims${queryString(filters)}`),
  reviewClaim: (id: string, input: { status: 'under_review' | 'approved' | 'rejected'; reason?: string }) => api<Claim>(`/staff/claims/${id}/status`, { method: 'PATCH', body: input }),
  handover: (id: string, notes?: string) => api<Handover>(`/staff/claims/${id}/handover`, { method: 'POST', body: { notes } }),
  custody: () => api<Page<CustodyRecord> | CustodyRecord[]>('/staff/custody'),
  takeCustody: (input: { report_id: string; storage_location: string; notes?: string }) => api<CustodyRecord>('/staff/custody', { method: 'POST', body: input }),
  updateCustody: (id: string, input: { storage_location?: string; notes?: string }) => api<CustodyRecord>(`/staff/custody/${id}`, { method: 'PATCH', body: input }),
  handovers: () => api<Page<Handover> | Handover[]>('/staff/handovers'),
}

export const adminApi = {
  dashboard: () => api<AdminDashboardData>('/admin/dashboard'),
  users: (page = 1, q = '') => api<Page<User>>(`/admin/users${queryString({ page, q, page_size: 30 })}`),
  updateUser: (id: string, input: { role?: string; is_active?: boolean }) => api<User>(`/admin/users/${id}`, { method: 'PATCH', body: input }),
  audit: (page = 1) => api<Page<AuditEvent>>(`/admin/audit-events${queryString({ page, page_size: 50 })}`),
  createCategory: (input: Partial<Category>) => api<Category>('/admin/categories', { method: 'POST', body: input }),
  updateCategory: (id: string, input: Partial<Category>) => api<Category>(`/admin/categories/${id}`, { method: 'PATCH', body: input }),
  deleteCategory: (id: string) => api<void>(`/admin/categories/${id}`, { method: 'DELETE' }),
  createLocation: (input: Partial<Location>) => api<Location>('/admin/locations', { method: 'POST', body: input }),
  updateLocation: (id: string, input: Partial<Location>) => api<Location>(`/admin/locations/${id}`, { method: 'PATCH', body: input }),
  deleteLocation: (id: string) => api<void>(`/admin/locations/${id}`, { method: 'DELETE' }),
}
