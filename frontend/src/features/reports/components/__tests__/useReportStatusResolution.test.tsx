import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getReportRuntimeStatus, getReportWithStatus, isRequestAbortError } from '@/lib/api/client'
import { recordClientMetric } from '@/lib/telemetry/clientMetrics'
import type { ResearchReport } from '@/lib/types/research'
import { useReportStatusResolution } from '../useReportStatusResolution'

vi.mock('@/lib/api/client', () => ({
  getReportRuntimeStatus: vi.fn(),
  getReportWithStatus: vi.fn(),
  isRequestAbortError: vi.fn(() => false),
}))

vi.mock('@/lib/telemetry/clientMetrics', () => ({
  recordClientMetric: vi.fn(),
}))

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
    cache_key: 'use-report-status-resolution',
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

describe('useReportStatusResolution', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    vi.mocked(isRequestAbortError).mockReturnValue(false)
  })

  it('retries post-stream processing states until the report becomes ready', async () => {
    vi.useFakeTimers()
    vi.mocked(getReportWithStatus)
      .mockResolvedValueOnce({ status: 'processing' })
      .mockResolvedValueOnce({ status: 'processing' })
      .mockResolvedValueOnce({ status: 'ready', report: reportFixture })

    const { result } = renderHook(() => useReportStatusResolution('r-ready'))

    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.loadPhase).toBe('processing')

    await act(async () => {
      const reconcilePromise = result.current.reconcileAfterStreamComplete()
      await Promise.resolve()
      await vi.advanceTimersByTimeAsync(250)
      await Promise.resolve()
      await reconcilePromise
    })

    expect(result.current.loadPhase).toBe('ready')
    expect(result.current.report?.id).toBe('r-ready')

    expect(getReportWithStatus).toHaveBeenCalledTimes(3)
    expect(recordClientMetric).toHaveBeenCalledWith(
      'report_stream_terminal_reconcile',
      expect.objectContaining({
        reportId: 'r-ready',
        initialStatus: 'processing',
        retryCount: 1,
        outcome: 'ready',
      }),
    )
  })

  it('records a reconcile metric when a missing report resolves to a failed runtime status', async () => {
    vi.mocked(getReportWithStatus)
      .mockResolvedValueOnce({ status: 'processing' })
      .mockResolvedValueOnce({ status: 'missing' })
    vi.mocked(getReportRuntimeStatus).mockResolvedValue({
      status: 'failed',
      report_id: 'r-failed',
      error_code: 'PIPELINE_FAILURE',
      message: 'Pipeline failed. Please retry.',
      query: 'Find AI meeting assistant',
    })

    const { result } = renderHook(() => useReportStatusResolution('r-failed'))

    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.loadPhase).toBe('processing')

    await act(async () => {
      await result.current.reconcileAfterStreamComplete()
      await Promise.resolve()
    })

    expect(result.current.loadPhase).toBe('ready')
    expect(result.current.runtimeStatus?.status).toBe('failed')
    expect(result.current.loadErrorKind).toBe('runtime')

    expect(recordClientMetric).toHaveBeenCalledWith(
      'report_stream_terminal_reconcile',
      expect.objectContaining({
        reportId: 'r-failed',
        initialStatus: 'missing',
        retryCount: 1,
        outcome: 'failed',
      }),
    )
  })
})
