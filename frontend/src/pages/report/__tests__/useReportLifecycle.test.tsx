import { act, renderHook, waitFor } from '@testing-library/react'
import type { NavigateFunction } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getReportRuntimeStatus, getReportWithStatus, startAnalysis } from '../../../api/client'
import { useSSE } from '../../../api/useSSE'
import { useReportLifecycle } from '../useReportLifecycle'

vi.mock('../../../api/client', () => ({
  cancelAnalysis: vi.fn(),
  getReportWithStatus: vi.fn(),
  getReportRuntimeStatus: vi.fn(),
  isRequestAbortError: vi.fn(() => false),
  startAnalysis: vi.fn(),
}))

vi.mock('../../../api/useSSE', () => ({
  useSSE: vi.fn(),
}))

describe('useReportLifecycle', () => {
  const navigate = vi.fn() as unknown as NavigateFunction

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSSE).mockReturnValue({
      events: [],
      isComplete: false,
      isReconnecting: false,
      error: null,
      cancelled: null,
      retry: vi.fn(),
    })
  })

  it('resolves missing report into failed runtime status', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({ status: 'missing' })
    vi.mocked(getReportRuntimeStatus).mockResolvedValue({
      status: 'failed',
      report_id: 'r-failed',
      error_code: 'PIPELINE_FAILURE',
      message: 'Pipeline failed. Please retry.',
      query: 'Find AI meeting assistant',
    })

    const { result } = renderHook(() => useReportLifecycle('r-failed', navigate))

    await waitFor(() => {
      expect(result.current.loadPhase).toBe('ready')
      expect(result.current.runtimeStatus?.status).toBe('failed')
    })
    expect(result.current.loadErrorKind).toBe('runtime')
    expect(result.current.loadError).toBe('Pipeline failed. Please retry.')
  })

  it('supports retry from cancelled runtime status after refresh', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({ status: 'missing' })
    vi.mocked(getReportRuntimeStatus).mockResolvedValue({
      status: 'cancelled',
      report_id: 'r-cancelled',
      error_code: 'PIPELINE_CANCELLED',
      message: 'Analysis cancelled by user',
      query: 'Local food delivery startup',
    })
    vi.mocked(startAnalysis).mockResolvedValue({ report_id: 'r-retry' })

    const { result } = renderHook(() => useReportLifecycle('r-cancelled', navigate))

    await waitFor(() => {
      expect(result.current.runtimeStatus?.status).toBe('cancelled')
    })

    act(() => {
      result.current.retryCurrentQuery()
    })

    await waitFor(() => {
      expect(startAnalysis).toHaveBeenCalledWith('Local food delivery startup')
      expect(navigate).toHaveBeenCalledWith('/reports/r-retry')
    })
  })
})
