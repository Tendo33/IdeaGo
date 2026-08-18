import {
  getAccessToken,
  setAccessToken,
} from '../auth/token'
import { readCurrentReturnTo } from '../auth/redirect'
import { supabase } from '../supabase/client'
import { clearHistoryCache } from '@/features/history/historyCache'

export const API_BASE = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1`
export const DEFAULT_TIMEOUT_MS = 15000
export const ANALYSIS_TIMEOUT_MS = 30000

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

export function authHeaders(): Record<string, string> {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export function mutationHeaders(): Record<string, string> {
  return { ...authHeaders(), 'X-Requested-With': 'IdeaGo' }
}

export interface RequestOptions {
  signal?: AbortSignal
  timeoutMs?: number
  allowUnauthorized?: boolean
  /** Internal: set on the replayed request so a 401 loop cannot form. */
  skipRefreshRetry?: boolean
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

export async function throwApiError(res: Response, prefix: string): Promise<never> {
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

export async function buildErrorMessage(res: Response, prefix: string): Promise<string> {
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

/**
 * Attempt a silent session renewal after a 401.
 *
 * The backend issues cookie-backed sessions and exposes `/auth/refresh` with a
 * grace period, but nothing ever called it: any 401 — including a transient one
 * from a Supabase JWKS blip — dumped the user straight to the login page and
 * discarded whatever they were doing.
 *
 * Concurrent 401s share one in-flight attempt so a burst of parallel requests
 * cannot stampede the refresh endpoint.
 */
let inFlightRefresh: Promise<boolean> | null = null

async function requestSessionRefresh(): Promise<boolean> {
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { ...authHeaders(), 'X-Requested-With': 'IdeaGo' },
    credentials: 'include',
  })
  if (!res.ok) return false
  try {
    const data = await res.json()
    if (typeof data?.access_token === 'string' && data.access_token) {
      setAccessToken(data.access_token)
    }
  } catch {
    // Cookie-backed sessions renew without a body; that is still a success.
  }
  return true
}

export function refreshSessionOnce(): Promise<boolean> {
  if (!inFlightRefresh) {
    inFlightRefresh = requestSessionRefresh()
      .catch(() => false)
      .finally(() => {
        inFlightRefresh = null
      })
  }
  return inFlightRefresh
}

/** Test seam: drop any in-flight refresh between cases. */
export function resetSessionRefreshState(): void {
  inFlightRefresh = null
}

function endSession(): never {
  setAccessToken(null)
  clearHistoryCache()
  supabase.auth.signOut().catch(() => {})
  const returnTo = encodeURIComponent(readCurrentReturnTo())
  window.location.href = `/login?returnTo=${returnTo}`
  throw new Error('Session expired. Redirecting to login.')
}

export async function fetchWithTimeout(
  url: string,
  init: RequestInit,
  options: RequestOptions,
  fallbackTimeoutMs: number,
): Promise<Response> {
  const res = await sendOnce(url, init, options, fallbackTimeoutMs)
  if (res.status !== 401 || options.allowUnauthorized || options.skipRefreshRetry) {
    return res
  }

  // One renewal attempt, then replay the original request. Only if that also
  // comes back 401 do we treat the session as genuinely gone.
  const renewed = await refreshSessionOnce()
  if (!renewed) endSession()

  const retried = await sendOnce(
    url,
    { ...init, headers: mergeAuthHeader(init.headers) },
    { ...options, skipRefreshRetry: true },
    fallbackTimeoutMs,
  )
  if (retried.status === 401) endSession()
  return retried
}

/** Re-stamp the Authorization header so the replay uses the renewed token. */
function mergeAuthHeader(headers: HeadersInit | undefined): HeadersInit | undefined {
  const token = getAccessToken()
  if (!token) return headers
  if (headers instanceof Headers) {
    const next = new Headers(headers)
    next.set('Authorization', `Bearer ${token}`)
    return next
  }
  if (Array.isArray(headers)) {
    return [...headers.filter(([key]) => key.toLowerCase() !== 'authorization'), [
      'Authorization',
      `Bearer ${token}`,
    ]]
  }
  return { ...(headers ?? {}), Authorization: `Bearer ${token}` }
}

async function sendOnce(
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
    return await fetch(url, {
      ...init,
      headers: init.headers,
      signal: timeoutController.signal,
      credentials: 'include',
    })
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
