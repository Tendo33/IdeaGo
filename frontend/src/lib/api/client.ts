import type { PaginatedReportList, ReportRuntimeStatus, ResearchReport } from '../types/research'

const API_BASE = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1`
const DEFAULT_TIMEOUT_MS = 15000
const ANALYSIS_TIMEOUT_MS = 30000

export class ApiError extends Error {
  readonly statusCode: number
  readonly code: string

  constructor(message: string, statusCode: number, code: string = '') {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.code = code
  }

  is(errorCode: string): boolean {
    return this.code === errorCode
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

export interface RequestOptions {
  signal?: AbortSignal
  timeoutMs?: number
}

export interface ListReportsOptions extends RequestOptions {
  limit?: number
  offset?: number
}

export function isRequestAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError'
}

interface ParsedError {
  message: string | null
  code: string
}

function mutationHeaders(): Record<string, string> {
  return { 'X-Requested-With': 'IdeaGo' }
}

function extractErrorDetail(payload: unknown): ParsedError {
  if (typeof payload === 'string' && payload.trim()) {
    return { message: payload.trim(), code: '' }
  }
  if (!payload || typeof payload !== 'object') {
    return { message: null, code: '' }
  }
  const record = payload as Record<string, unknown>
  const detail = record.detail
  if (typeof detail === 'string' && detail.trim()) {
    return { message: detail.trim(), code: '' }
  }
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>
    return {
      message: typeof d.message === 'string' ? d.message.trim() : null,
      code: typeof d.code === 'string' ? d.code.trim() : '',
    }
  }
  const error = record.error
  if (error && typeof error === 'object') {
    const e = error as Record<string, unknown>
    return {
      message: typeof e.message === 'string' ? e.message.trim() : null,
      code: typeof e.code === 'string' ? e.code.trim() : '',
    }
  }
  if (typeof error === 'string' && error.trim()) {
    return { message: error.trim(), code: '' }
  }
  const message = record.message
  if (typeof message === 'string' && message.trim()) {
    return { message: message.trim(), code: '' }
  }
  return { message: null, code: '' }
}

async function throwApiError(res: Response, prefix: string): Promise<never> {
  let parsed: ParsedError = { message: null, code: '' }
  if (typeof res.json === 'function') {
    try {
      const payload = await res.json()
      parsed = extractErrorDetail(payload)
    } catch {
      // fall back to status code
    }
  }
  const msg = `${prefix}: ${parsed.message ?? res.status}`
  throw new ApiError(msg, res.status, parsed.code)
}

async function buildErrorMessage(res: Response, prefix: string): Promise<string> {
  let parsed: ParsedError = { message: null, code: '' }
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
    return await fetch(url, {
      ...init,
      headers: init.headers,
      signal: timeoutController.signal,
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
  const res = await fetchWithTimeout(`${API_BASE}/reports/${id}`, {}, options, DEFAULT_TIMEOUT_MS)
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
  const res = await fetchWithTimeout(`${API_BASE}/reports/${id}`, {}, options, DEFAULT_TIMEOUT_MS)
  if (res.status === 202) return { status: 'processing' }
  if (res.status === 404) return { status: 'missing' }
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Report not found'))
  return { status: 'ready', report: await res.json() }
}

export async function getReportRuntimeStatus(
  id: string,
  options: RequestOptions = {},
): Promise<ReportRuntimeStatus> {
  const res = await fetchWithTimeout(`${API_BASE}/reports/${id}/status`, {}, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load report status'))
  return res.json()
}

export async function listReports(options: ListReportsOptions = {}): Promise<PaginatedReportList> {
  const { limit, offset, ...requestOptions } = options
  const params = new URLSearchParams()
  if (typeof limit === 'number') {
    params.set('limit', String(limit))
  }
  if (typeof offset === 'number') {
    params.set('offset', String(offset))
  }
  const query = params.toString()
  const url = query ? `${API_BASE}/reports?${query}` : `${API_BASE}/reports`
  const res = await fetchWithTimeout(url, {}, requestOptions, DEFAULT_TIMEOUT_MS)
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
    {},
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
