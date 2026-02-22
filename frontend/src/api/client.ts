import type { ReportListItem, ResearchReport } from '../types/research'

const API_BASE = `${import.meta.env.VITE_API_BASE_URL ?? ''}/api/v1`

export async function startAnalysis(query: string): Promise<{ report_id: string }> {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })
  if (!res.ok) throw new Error(`Analysis failed: ${res.status}`)
  return res.json()
}

export async function getReport(id: string): Promise<ResearchReport> {
  const res = await fetch(`${API_BASE}/reports/${id}`)
  if (!res.ok) throw new Error(`Report not found: ${res.status}`)
  return res.json()
}

export async function listReports(): Promise<ReportListItem[]> {
  const res = await fetch(`${API_BASE}/reports`)
  if (!res.ok) throw new Error(`Failed to list reports: ${res.status}`)
  return res.json()
}

export async function deleteReport(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/reports/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete report: ${res.status}`)
}

export async function cancelAnalysis(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/reports/${id}/cancel`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to cancel analysis: ${res.status}`)
}

export function getExportUrl(id: string): string {
  return `${API_BASE}/reports/${id}/export`
}

export function getStreamUrl(id: string): string {
  return `${API_BASE}/reports/${id}/stream`
}
