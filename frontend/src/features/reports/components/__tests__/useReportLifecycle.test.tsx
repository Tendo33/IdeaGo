import { act, renderHook, waitFor } from '@testing-library/react'
import type { NavigateFunction } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getReportRuntimeStatus, getReportWithStatus, startAnalysis } from '@/lib/api/client'
import { useSSE } from '@/lib/api/useSSE'
import { useReportLifecycle } from '../useReportLifecycle'
import type { ResearchReport } from '@/lib/types/research'

vi.mock('@/lib/api/client', () => ({
  cancelAnalysis: vi.fn(),
  getReportWithStatus: vi.fn(),
  getReportRuntimeStatus: vi.fn(),
  isRequestAbortError: vi.fn(() => false),
  startAnalysis: vi.fn(),
}))

vi.mock('@/lib/api/useSSE', () => ({
  useSSE: vi.fn(),
}))

describe('useReportLifecycle', () => {
  const navigate = vi.fn() as unknown as NavigateFunction
  const reportFixture: ResearchReport = {
    id: 'r-ready',
    query: 'Niche AI assistant for legal teams',
    intent: {
      keywords_en: ['ai', 'assistant'],
      keywords_zh: [],
      exact_entities: [],
      comparison_anchors: [],
      search_goal: 'validate',
      app_type: 'web',
      target_scenario: 'legal workflow',
      output_language: 'en',
      search_queries: [],
      cache_key: 'use-report-lifecycle',
    },
    source_results: [],
    competitors: [],
    pain_signals: [],
    commercial_signals: [],
    whitespace_opportunities: [],
    opportunity_score: {
      pain_intensity: 0,
      solution_gap: 0,
      commercial_intent: 0,
      freshness: 0,
      competition_density: 0,
      score: 0,
    },
    market_summary: 'summary',
    go_no_go: 'go',
    recommendation_type: 'go',
    differentiation_angles: [],
    confidence: {
      sample_size: 0,
      source_coverage: 0,
      source_success_rate: 0,
      source_diversity: 0,
      evidence_density: 0,
      recency_score: 0,
      degradation_penalty: 0,
      contradiction_penalty: 0,
      reasons: [],
      freshness_hint: 'Fresh',
      score: 0,
    },
    evidence_summary: {
      top_evidence: [],
      evidence_items: [],
      category_counts: {},
      source_platforms: [],
      freshness_distribution: {},
      degraded_sources: [],
      uncertainty_notes: [],
    },
    cost_breakdown: {
      llm_calls: 0,
      llm_retries: 0,
      endpoint_failovers: 0,
      source_calls: 0,
      pipeline_latency_ms: 0,
      tokens_prompt: 0,
      tokens_completion: 0,
    },
    report_meta: {
      llm_fault_tolerance: {
        fallback_used: false,
        endpoints_tried: ['primary'],
        last_error_class: '',
      },
      quality_warnings: [],
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
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

  it('falls back to the home route when restart is requested without a recoverable query', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({ status: 'missing' })
    vi.mocked(getReportRuntimeStatus).mockResolvedValue({
      status: 'failed',
      report_id: 'r-failed-no-query',
      error_code: 'PIPELINE_FAILURE',
      message: 'Pipeline failed.',
      query: null,
    })

    const { result } = renderHook(() => useReportLifecycle('r-failed-no-query', navigate))

    await waitFor(() => {
      expect(result.current.runtimeStatus?.status).toBe('failed')
    })

    act(() => {
      result.current.retryCurrentQuery()
    })

    expect(startAnalysis).not.toHaveBeenCalled()
    expect(navigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('polls runtime status when stream completes but report is still missing', async () => {
    vi.mocked(useSSE).mockReturnValue({
      events: [],
      isComplete: true,
      isReconnecting: false,
      error: null,
      cancelled: null,
      retry: vi.fn(),
    })

    vi.mocked(getReportWithStatus)
      .mockResolvedValueOnce({ status: 'processing' })
      .mockResolvedValueOnce({ status: 'missing' })
      .mockResolvedValueOnce({ status: 'ready', report: reportFixture })
    vi.mocked(getReportRuntimeStatus)
      .mockResolvedValueOnce({
        status: 'processing',
        report_id: 'r-ready',
        query: reportFixture.query,
      })
      .mockResolvedValueOnce({
        status: 'complete',
        report_id: 'r-ready',
        query: reportFixture.query,
      })

    const { result } = renderHook(() => useReportLifecycle('r-ready', navigate))

    await waitFor(() => {
      expect(result.current.loadPhase).toBe('ready')
      expect(result.current.report?.id).toBe('r-ready')
    })

    expect(getReportRuntimeStatus).toHaveBeenCalledTimes(2)
  })

  it('marks complete-but-unavailable reports as terminal and restartable', async () => {
    vi.mocked(useSSE).mockReturnValue({
      events: [],
      isComplete: true,
      isReconnecting: false,
      error: null,
      cancelled: null,
      retry: vi.fn(),
    })

    vi.mocked(getReportWithStatus)
      .mockResolvedValueOnce({ status: 'processing' })
      .mockResolvedValueOnce({ status: 'missing' })
      .mockResolvedValue({ status: 'missing' })
    vi.mocked(getReportRuntimeStatus)
      .mockResolvedValueOnce({
        status: 'complete',
        report_id: 'r-unavailable',
        query: 'AI assistant for dentists',
      })
      .mockResolvedValueOnce({
        status: 'complete',
        report_id: 'r-unavailable',
        query: 'AI assistant for dentists',
      })
      .mockResolvedValueOnce({
        status: 'complete',
        report_id: 'r-unavailable',
        query: 'AI assistant for dentists',
      })
    vi.mocked(startAnalysis).mockResolvedValue({ report_id: 'r-regenerated' })

    const { result } = renderHook(() => useReportLifecycle('r-unavailable', navigate))

    await waitFor(() => {
      expect(result.current.loadPhase).toBe('ready')
      expect(result.current.runtimeStatus?.status).toBe('complete')
      expect(result.current.loadErrorKind).toBe('system')
    })

    act(() => {
      result.current.retryErrorState()
    })

    await waitFor(() => {
      expect(startAnalysis).toHaveBeenCalledWith('AI assistant for dentists')
      expect(navigate).toHaveBeenCalledWith('/reports/r-regenerated')
    })
  })

  it('keeps connection errors separate from runtime-status errors', async () => {
    vi.mocked(useSSE).mockReturnValue({
      events: [],
      isComplete: false,
      isReconnecting: false,
      error: 'Connection lost',
      cancelled: null,
      retry: vi.fn(),
    })
    vi.mocked(getReportWithStatus).mockResolvedValue({ status: 'processing' })

    const { result } = renderHook(() => useReportLifecycle('r-processing', navigate))

    await waitFor(() => {
      expect(result.current.sseError).toBe('Connection lost')
    })
    expect(result.current.loadError).toBeNull()
    expect(result.current.loadErrorKind).toBeNull()
  })
})
