import type { PaginatedReportList, ReportRuntimeStatus, ResearchReport } from '../types/research'
import {
  getAccessToken,
  setAccessToken,
} from '../auth/token'
import { readCurrentReturnTo } from '../auth/redirect'
import { supabase } from '../supabase/client'

const API_BASE = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1`
const DEFAULT_TIMEOUT_MS = 15000
const ANALYSIS_TIMEOUT_MS = 30000

export class ApiError extends Error {
  readonly statusCode: number
  readonly code: string
  readonly detail: Record<string, unknown>

  constructor(message: string, statusCode: number, code: string = '', detail: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.code = code
    this.detail = detail
  }

  is(errorCode: string): boolean {
    return this.code === errorCode
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

function authHeaders(): Record<string, string> {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function mutationHeaders(): Record<string, string> {
  return { ...authHeaders(), 'X-Requested-With': 'IdeaGo' }
}

export interface RequestOptions {
  signal?: AbortSignal
  timeoutMs?: number
  allowUnauthorized?: boolean
}

export interface ListReportsOptions extends RequestOptions {
  limit?: number
  offset?: number
  q?: string
}

export function isRequestAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

interface ParsedError {
  message: string | null
  code: string
  detail: Record<string, unknown>
}

function extractErrorDetail(payload: unknown): ParsedError {
  if (typeof payload === 'string' && payload.trim()) {
    return { message: payload.trim(), code: '', detail: {} }
  }
  if (!payload || typeof payload !== 'object') {
    return { message: null, code: '', detail: {} }
  }
  const record = payload as Record<string, unknown>
  const detail = record.detail
  if (typeof detail === 'string' && detail.trim()) {
    return { message: detail.trim(), code: '', detail: {} }
  }
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>
    return {
      message: typeof d.message === 'string' ? d.message.trim() : null,
      code: typeof d.code === 'string' ? d.code.trim() : '',
      detail: d,
    }
  }
  const error = record.error
  if (error && typeof error === 'object') {
    const e = error as Record<string, unknown>
    return {
      message: typeof e.message === 'string' ? e.message.trim() : null,
      code: typeof e.code === 'string' ? e.code.trim() : '',
      detail: e,
    }
  }
  if (typeof error === 'string' && error.trim()) {
    return { message: error.trim(), code: '', detail: {} }
  }
  const message = record.message
  if (typeof message === 'string' && message.trim()) {
    return { message: message.trim(), code: '', detail: {} }
  }
  return { message: null, code: '', detail: {} }
}

async function throwApiError(res: Response, prefix: string): Promise<never> {
  let parsed: ParsedError = { message: null, code: '', detail: {} }
  if (typeof res.json === 'function') {
    try {
      const payload = await res.json()
      parsed = extractErrorDetail(payload)
    } catch {
      // fall back to status code
    }
  }
  const msg = `${prefix}: ${parsed.message ?? res.status}`
  throw new ApiError(msg, res.status, parsed.code, parsed.detail)
}

async function buildErrorMessage(res: Response, prefix: string): Promise<string> {
  let parsed: ParsedError = { message: null, code: '', detail: {} }
  if (typeof res.json === 'function') {
    try {
      const payload = await res.json()
      parsed = extractErrorDetail(payload)
    } catch {
      // fall back to status code
    }
  }
  return `${prefix}: ${parsed.message ?? res.status}`
}

async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  options: RequestOptions,
  fallbackTimeoutMs: number,
): Promise<Response> {
  const timeoutMs = options.timeoutMs ?? fallbackTimeoutMs
  const timeoutController = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    timeoutController.abort()
  }, timeoutMs)

  const propagateAbort = () => timeoutController.abort()
  if (options.signal) {
    if (options.signal.aborted) {
      clearTimeout(timer)
      throw new DOMException('Aborted', 'AbortError')
    }
    options.signal.addEventListener('abort', propagateAbort)
  }

  try {
    const res = await fetch(url, {
      ...init,
      headers: init.headers,
      signal: timeoutController.signal,
      credentials: 'include',
    })
    if (res.status === 401) {
      if (options.allowUnauthorized) {
        return res
      }
      setAccessToken(null)
      supabase.auth.signOut().catch(() => {})
      const returnTo = encodeURIComponent(readCurrentReturnTo())
      window.location.href = `/login?returnTo=${returnTo}`
      throw new Error('Session expired. Redirecting to login.')
    }
    return res
  } catch (error) {
    if (isRequestAbortError(error) && timedOut) {
      throw new Error('Request timed out. Please try again.')
    }
    throw error
  } finally {
    clearTimeout(timer)
    if (options.signal) {
      options.signal.removeEventListener('abort', propagateAbort)
    }
  }
}

export async function startAnalysis(
  query: string,
  options: RequestOptions = {},
): Promise<{ report_id: string }> {
  const res = await fetchWithTimeout(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...mutationHeaders() },
    body: JSON.stringify({ query }),
  }, options, ANALYSIS_TIMEOUT_MS)
  if (!res.ok) await throwApiError(res, 'Analysis failed')
  return res.json()
}

export async function getReport(
  id: string,
  options: RequestOptions = {},
): Promise<ResearchReport> {
  const res = await fetchWithTimeout(`${API_BASE}/reports/${id}`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Report not found'))
  return res.json()
}

export type ReportFetchResult =
  | { status: 'ready'; report: ResearchReport }
  | { status: 'processing' }
  | { status: 'missing' }

export async function getReportWithStatus(
  id: string,
  options: RequestOptions = {},
): Promise<ReportFetchResult> {
  const res = await fetchWithTimeout(`${API_BASE}/reports/${id}`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (res.status === 202) return { status: 'processing' }
  if (res.status === 404) return { status: 'missing' }
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Report not found'))
  return { status: 'ready', report: await res.json() }
}

export async function getReportRuntimeStatus(
  id: string,
  options: RequestOptions = {},
): Promise<ReportRuntimeStatus> {
  const res = await fetchWithTimeout(`${API_BASE}/reports/${id}/status`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load report status'))
  return res.json()
}

export async function listReports(options: ListReportsOptions = {}): Promise<PaginatedReportList> {
  const { limit, offset, q, ...requestOptions } = options
  const params = new URLSearchParams()
  if (typeof limit === 'number') {
    params.set('limit', String(limit))
  }
  if (typeof offset === 'number') {
    params.set('offset', String(offset))
  }
  if (typeof q === 'string' && q.trim().length > 0) {
    params.set('q', q.trim())
  }
  const query = params.toString()
  const url = query ? `${API_BASE}/reports?${query}` : `${API_BASE}/reports`
  const res = await fetchWithTimeout(url, { headers: authHeaders() }, requestOptions, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to list reports'))
  return res.json()
}

export async function deleteReport(id: string, options: RequestOptions = {}): Promise<void> {
  const res = await fetchWithTimeout(`${API_BASE}/reports/${id}`, { method: 'DELETE', headers: mutationHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to delete report'))
}

export async function cancelAnalysis(id: string, options: RequestOptions = {}): Promise<void> {
  const res = await fetchWithTimeout(`${API_BASE}/reports/${id}/cancel`, { method: 'DELETE', headers: mutationHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to cancel analysis'))
}

export async function exportReport(id: string, options: RequestOptions = {}): Promise<void> {
  const res = await fetchWithTimeout(
    `${API_BASE}/reports/${id}/export`,
    { headers: authHeaders() },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Export failed'))
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `report-${id.slice(0, 8)}.md`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export function getStreamUrl(id: string): string {
  return `${API_BASE}/reports/${id}/stream`
}

export interface QuotaInfo {
  usage_count: number
  plan_limit: number
  plan: string
  reset_at?: string
  error?: string
}

export interface UserProfile {
  display_name: string
  avatar_url: string
  bio: string
  created_at: string
  role?: string
}

export interface DeleteAccountResult {
  status: 'deleted'
  cleanup: {
    domain_data: string
    billing: string
    auth_identity: string
  }
}

export async function refreshAuthToken(options: RequestOptions = {}): Promise<string> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/refresh`,
    { method: 'POST', headers: mutationHeaders() },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Token refresh failed'))
  const data = await res.json()
  return data.access_token
}

export interface StartLinuxDoAuthOptions {
  redirectTo: string
  captchaToken: string
}

export async function startLinuxDoAuth(
  { redirectTo, captchaToken }: StartLinuxDoAuthOptions,
  options: RequestOptions = {},
): Promise<string> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/linuxdo/start`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...mutationHeaders(),
      },
      body: JSON.stringify({
        redirect_to: redirectTo,
        captcha_token: captchaToken,
        prefetch: true,
      }),
    },
    { ...options, allowUnauthorized: true },
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'LinuxDo login failed'))
  const data = await res.json()
  const url = typeof data?.url === 'string' ? data.url.trim() : ''
  if (!url) {
    throw new Error('LinuxDo login failed: Missing authorize URL')
  }
  return url
}

export interface CurrentUser {
  id: string
  email: string
}

export async function getMe(options: RequestOptions = {}): Promise<CurrentUser> {
  const res = await fetchWithTimeout(`${API_BASE}/auth/me`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load current user'))
  return res.json()
}

export async function logoutAuthSession(options: RequestOptions = {}): Promise<void> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/logout`,
    { method: 'POST', headers: mutationHeaders() },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to logout'))
}

export async function getQuotaInfo(options: RequestOptions = {}): Promise<QuotaInfo> {
  const res = await fetchWithTimeout(`${API_BASE}/auth/quota`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load quota'))
  return res.json()
}

export async function getMyProfile(options: RequestOptions = {}): Promise<UserProfile> {
  const res = await fetchWithTimeout(`${API_BASE}/auth/profile`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load profile'))
  return res.json()
}

export async function updateMyProfile(
  payload: Pick<UserProfile, 'display_name' | 'bio'>,
  options: RequestOptions = {},
): Promise<UserProfile> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/profile`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...mutationHeaders() },
      body: JSON.stringify(payload),
    },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to update profile'))
  return res.json()
}

export async function deleteAccount(options: RequestOptions = {}): Promise<DeleteAccountResult> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/account`,
    { method: 'DELETE', headers: mutationHeaders() },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) await throwApiError(res, 'Failed to delete account')
  return res.json()
}

// --- Billing ---

export interface SubscriptionStatus {
  plan: string
  has_subscription: boolean
  stripe_configured: boolean
}

export async function getSubscriptionStatus(options: RequestOptions = {}): Promise<SubscriptionStatus> {
  const res = await fetchWithTimeout(`${API_BASE}/billing/status`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load subscription status'))
  return res.json()
}

export async function createCheckoutSession(
  successUrl: string,
  cancelUrl: string,
  options: RequestOptions = {},
): Promise<string> {
  const res = await fetchWithTimeout(
    `${API_BASE}/billing/checkout`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...mutationHeaders() },
      body: JSON.stringify({ success_url: successUrl, cancel_url: cancelUrl }),
    },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to create checkout'))
  const data = await res.json()
  return data.url
}

export async function createPortalSession(
  returnUrl: string,
  options: RequestOptions = {},
): Promise<string> {
  const res = await fetchWithTimeout(
    `${API_BASE}/billing/portal`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...mutationHeaders() },
      body: JSON.stringify({ return_url: returnUrl }),
    },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to create portal session'))
  const data = await res.json()
  return data.url
}

// --- Admin ---

export interface AdminUser {
  id: string
  display_name: string
  avatar_url: string
  bio: string
  created_at: string
  plan: string
  usage_count: number
  plan_limit: number
  role: string
  auth_provider: string
}

export interface AdminStats {
  total_users: number
  total_reports: number
  active_processing: number
  plan_breakdown: Record<string, number>
}

export async function adminListUsers(
  options: RequestOptions & { limit?: number; offset?: number } = {},
): Promise<AdminUser[]> {
  const { limit, offset, ...rest } = options
  const params = new URLSearchParams()
  if (typeof limit === 'number') params.set('limit', String(limit))
  if (typeof offset === 'number') params.set('offset', String(offset))
  const query = params.toString()
  const url = query ? `${API_BASE}/admin/users?${query}` : `${API_BASE}/admin/users`
  const res = await fetchWithTimeout(url, { headers: authHeaders() }, rest, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to list users'))
  return res.json()
}

export async function adminGetStats(options: RequestOptions = {}): Promise<AdminStats> {
  const res = await fetchWithTimeout(`${API_BASE}/admin/stats`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load stats'))
  return res.json()
}

export async function adminSetQuota(
  userId: string,
  payload: { plan_limit?: number; usage_count?: number },
  options: RequestOptions = {},
): Promise<void> {
  const res = await fetchWithTimeout(
    `${API_BASE}/admin/users/${userId}/quota`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...mutationHeaders() },
      body: JSON.stringify(payload),
    },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to update quota'))
}
