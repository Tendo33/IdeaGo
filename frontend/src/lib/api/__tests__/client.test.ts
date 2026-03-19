import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  startAnalysis,
  getReport,
  getReportWithStatus,
  getReportRuntimeStatus,
  listReports,
  deleteReport,
  cancelAnalysis,
  exportReport,
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

  it('prefers backend error detail when present', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ detail: 'Query too short after whitespace normalization' }),
    })

    await expect(startAnalysis('test')).rejects.toThrow(
      'Analysis failed: Query too short after whitespace normalization',
    )
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
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/r1'),
      expect.objectContaining({ signal: expect.anything() }),
    )
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

  it('returns missing on 404', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 })
    const result = await getReportWithStatus('missing')
    expect(result).toEqual({ status: 'missing' })
  })
})

describe('getReportRuntimeStatus', () => {
  it('returns runtime status payload', async () => {
    const payload = {
      status: 'failed',
      report_id: 'r1',
      error_code: 'PIPELINE_FAILURE',
      message: 'Pipeline failed. Please retry.',
      updated_at: '2026-02-28T12:00:00Z',
      query: 'test query',
    }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    })

    const result = await getReportRuntimeStatus('r1')

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/r1/status'),
      expect.objectContaining({ signal: expect.anything() }),
    )
    expect(result).toEqual(payload)
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
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports'),
      expect.objectContaining({ signal: expect.anything() }),
    )
    expect(result).toEqual(reports)
  })

  it('supports limit and offset query parameters', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    })

    await listReports({ limit: 5, offset: 20 })

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/reports\?limit=5&offset=20$/),
      expect.objectContaining({ signal: expect.anything() }),
    )
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

  it('uses backend detail on failure when available', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: 'No active analysis found for this report' }),
    })
    await expect(cancelAnalysis('r1')).rejects.toThrow(
      'Failed to cancel analysis: No active analysis found for this report',
    )
  })
})

describe('URL helpers', () => {
  it('exportReport fetches with auth and triggers download', async () => {
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:fake', revokeObjectURL })

    const mockLink = { href: '', download: '', click: vi.fn(), remove: vi.fn() }
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLElement)
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as unknown as Node)

    mockFetch.mockResolvedValueOnce({ ok: true, blob: () => Promise.resolve(new Blob(['# Report'])) })
    await exportReport('abc')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/abc/export'),
      expect.objectContaining({ headers: expect.any(Object) }),
    )
    expect(mockLink.click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake')
  })

  it('getStreamUrl builds correct URL', () => {
    expect(getStreamUrl('abc')).toContain('/api/v1/reports/abc/stream')
  })
})
