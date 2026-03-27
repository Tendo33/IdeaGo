import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ResearchReport } from '@/lib/types/research'
import { ReportPage } from '../ReportPage'
import { getReportRuntimeStatus, getReportWithStatus } from '@/lib/api/client'
import { useSSE } from '@/lib/api/useSSE'

vi.mock('@/lib/api/client', () => ({
  isApiError: () => false,
  isRequestAbortError: () => false,
  getReportWithStatus: vi.fn(),
  getReportRuntimeStatus: vi.fn(),
  cancelAnalysis: vi.fn(),
  startAnalysis: vi.fn(),
}))

vi.mock('@/lib/api/useSSE', () => ({
  useSSE: vi.fn(),
}))

vi.mock('@/features/reports/components/ReportProgressPane', () => ({
  ReportProgressPane: () => null,
}))

vi.mock('@/features/reports/components/ReportErrorBanner', () => ({
  ReportErrorBanner: () => null,
}))

vi.mock('@/features/reports/components/ReportContentPane', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return {
    ReportContentPane: () => <div>REPORT_CONTENT</div>,
  }
})

const REPORT: ResearchReport = {
  id: 'report-performance',
  query: 'performance report',
  intent: {
    keywords_en: ['performance'],
    keywords_zh: [],
    app_type: 'web',
    target_scenario: '',
    output_language: 'en',
    search_queries: [],
    cache_key: 'report-performance',
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
  market_summary: '',
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
    freshness_hint: '',
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

describe('ReportPage performance behavior', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getReportRuntimeStatus).mockResolvedValue({
      status: 'complete',
      report_id: 'report-performance',
      query: REPORT.query,
    })
    vi.mocked(useSSE).mockReturnValue({
      events: [],
      isComplete: true,
      isReconnecting: false,
      error: null,
      cancelled: null,
      retry: vi.fn(),
    })
  })

  it('shows a fallback while report content chunk is loading', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: REPORT,
    })

    render(
      <MemoryRouter initialEntries={['/reports/report-performance']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('report-content-loading')).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText('REPORT_CONTENT')).toBeInTheDocument()
    })
  })
})
