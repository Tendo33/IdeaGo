import type { PaginatedReportList, ReportRuntimeStatus, ResearchReport } from '../types/research'
import {
  ANALYSIS_TIMEOUT_MS,
  API_BASE,
  DEFAULT_TIMEOUT_MS,
  authHeaders,
  buildErrorMessage,
  fetchWithTimeout,
  mutationHeaders,
  type ListReportsOptions,
  type RequestOptions,
  throwApiError,
} from './core'

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
