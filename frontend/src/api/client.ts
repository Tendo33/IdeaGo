import type { ReportListItem, ResearchReport } from '../types/research'

const API_BASE = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1`

function extractErrorDetail(payload: unknown): string | null {
  if (typeof payload === 'string' && payload.trim()) {
    return payload.trim()
  }
  if (!payload || typeof payload !== 'object') {
    return null
  }
  const record = payload as Record<string, unknown>
  const detail = record.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  const error = record.error
  if (typeof error === 'string' && error.trim()) {
    return error.trim()
  }
  const message = record.message
  if (typeof message === 'string' && message.trim()) {
    return message.trim()
  }
  return null
}

async function buildErrorMessage(res: Response, prefix: string): Promise<string> {
  let detail: string | null = null
  if (typeof res.json === 'function') {
    try {
      const payload = await res.json()
      detail = extractErrorDetail(payload)
    } catch {
      // Ignore JSON parse failures and fall back to status code.
    }
  }
  return `${prefix}: ${detail ?? res.status}`
}

export async function startAnalysis(query: string): Promise<{ report_id: string }> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Analysis failed'))
  return res.json()
}

export async function getReport(id: string): Promise<ResearchReport> {
  const res = await fetch(`${API_BASE}/reports/${id}`)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Report not found'))
  return res.json()
}

export type ReportFetchResult =
  | { status: 'ready'; report: ResearchReport }
  | { status: 'processing' }

export async function getReportWithStatus(id: string): Promise<ReportFetchResult> {
  const res = await fetch(`${API_BASE}/reports/${id}`)
  if (res.status === 202) return { status: 'processing' }
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Report not found'))
  return { status: 'ready', report: await res.json() }
}

export async function listReports(): Promise<ReportListItem[]> {
  const res = await fetch(`${API_BASE}/reports`)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to list reports'))
  return res.json()
}

export async function deleteReport(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/reports/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to delete report'))
}

export async function cancelAnalysis(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/reports/${id}/cancel`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to cancel analysis'))
}

export function getExportUrl(id: string): string {
  return `${API_BASE}/reports/${id}/export`
}

export function getStreamUrl(id: string): string {
  return `${API_BASE}/reports/${id}/stream`
}
