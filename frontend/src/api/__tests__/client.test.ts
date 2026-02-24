import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  startAnalysis,
  getReport,
  getReportWithStatus,
  listReports,
  deleteReport,
  cancelAnalysis,
  getExportUrl,
  getStreamUrl,
} from '../client'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
})

describe('startAnalysis', () => {
  it('sends POST with query and returns report_id', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ report_id: 'abc-123' }),
    })

    const result = await startAnalysis('my startup idea')

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/analyze'),
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'my startup idea' }),
      }),
    )
    expect(result).toEqual({ report_id: 'abc-123' })
  })

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 429 })
    await expect(startAnalysis('test')).rejects.toThrow('Analysis failed: 429')
  })
})

describe('getReport', () => {
  it('fetches report by id', async () => {
    const report = { id: 'r1', query: 'test' }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(report),
    })

    const result = await getReport('r1')
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/api/v1/reports/r1'))
    expect(result).toEqual(report)
  })

  it('throws on 404', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 })
    await expect(getReport('missing')).rejects.toThrow('Report not found: 404')
  })
})

describe('getReportWithStatus', () => {
  it('returns processing on 202', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 202 })
    const result = await getReportWithStatus('pending')
    expect(result).toEqual({ status: 'processing' })
  })

  it('returns ready with report on 200', async () => {
    const report = { id: 'r1', query: 'test' }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(report),
    })
    const result = await getReportWithStatus('r1')
    expect(result).toEqual({ status: 'ready', report })
  })
})

describe('listReports', () => {
  it('returns list of reports', async () => {
    const reports = [{ id: 'r1', query: 'test', created_at: '2026-01-01', competitor_count: 3 }]
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(reports),
    })

    const result = await listReports()
    expect(mockFetch).toHaveBeenCalledWith(expect.stringContaining('/api/v1/reports'))
    expect(result).toEqual(reports)
  })
})

describe('deleteReport', () => {
  it('sends DELETE request', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true })

    await deleteReport('r1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/r1'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('throws on failure', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500 })
    await expect(deleteReport('r1')).rejects.toThrow('Failed to delete report: 500')
  })
})

describe('cancelAnalysis', () => {
  it('sends DELETE request to cancel endpoint', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true })

    await cancelAnalysis('r1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/r1/cancel'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('throws on failure', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 })
    await expect(cancelAnalysis('r1')).rejects.toThrow('Failed to cancel analysis: 404')
  })
})

describe('URL helpers', () => {
  it('getExportUrl builds correct URL', () => {
    expect(getExportUrl('abc')).toContain('/api/v1/reports/abc/export')
  })

  it('getStreamUrl builds correct URL', () => {
    expect(getStreamUrl('abc')).toContain('/api/v1/reports/abc/stream')
  })
})
