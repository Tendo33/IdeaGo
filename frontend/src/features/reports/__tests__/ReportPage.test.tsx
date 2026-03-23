import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ReportPage } from '../ReportPage'
import { getReportRuntimeStatus, getReportWithStatus, startAnalysis } from '@/lib/api/client'
import { useSSE } from '@/lib/api/useSSE'
import i18n from '@/lib/i18n/i18n'
import type { ResearchReport } from '@/lib/types/research'
import { ApiError } from '@/lib/api/client'

vi.mock('@/lib/api/client', () => ({
  ApiError: class ApiError extends Error {
    statusCode: number
    code: string

    constructor(message: string, statusCode: number, code = '') {
      super(message)
      this.name = 'ApiError'
      this.statusCode = statusCode
      this.code = code
    }

    is(errorCode: string) {
      return this.code === errorCode
    }
  },
  isApiError: (error: unknown) => error instanceof Error && error.name === 'ApiError',
  isRequestAbortError: (error: unknown) => error instanceof Error && error.name === 'AbortError',
  getReportWithStatus: vi.fn(),
  getReportRuntimeStatus: vi.fn(),
  cancelAnalysis: vi.fn(),
  startAnalysis: vi.fn(),
  exportReport: vi.fn(),
}))

vi.mock('@/lib/api/useSSE', () => ({
  useSSE: vi.fn(),
}))

vi.mock('@/features/reports/components/HorizontalStepper', () => ({ HorizontalStepper: () => <div>STEPPER</div> }))
vi.mock('@/features/reports/components/ReportHeader', () => ({
  ReportHeader: ({ report }: { report: { query: string } }) => <div>{`HEADER:${report.query}`}</div>,
}))
vi.mock('@/features/home/components/HeroPanel', () => ({ HeroPanel: () => <div>HERO</div> }))
vi.mock('@/features/reports/components/ConfidenceCard', () => ({ ConfidenceCard: () => <div>CONFIDENCE</div> }))
vi.mock('@/features/reports/components/EvidenceCostCard', () => ({ EvidenceCostCard: () => <div>EVIDENCE_COST</div> }))
vi.mock('@/features/reports/components/MarketOverview', () => ({ MarketOverview: () => <div>MARKET</div> }))
vi.mock('@/features/reports/components/CompetitorCard', () => ({ CompetitorCard: () => <div>CARD</div> }))
vi.mock('@/features/reports/components/CompetitorRow', () => ({ CompetitorRow: () => <div>ROW</div> }))
vi.mock('@/features/reports/components/LandscapeChart', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return { LandscapeChart: () => <div>CHART</div> }
})
vi.mock('@/features/reports/components/InsightCard', () => ({ InsightsSection: () => <div>INSIGHTS</div> }))
vi.mock('@/features/reports/components/ComparePanel', () => ({
  ComparePanel: () => <div>COMPARE</div>,
  CompareFloatingBar: () => <div>FLOATING</div>,
}))
vi.mock('@/features/reports/components/SectionNav', () => ({ SectionNav: () => <div>NAV</div> }))
vi.mock('@/components/ui/Skeleton', () => ({
  Skeleton: () => <div>SKELETON</div>,
  CompetitorCardSkeleton: () => <div>CARD-SKELETON</div>,
}))

const BASE_REPORT: ResearchReport = {
  id: 'base-report',
  query: 'base query',
  intent: {
    keywords_en: ['idea'],
    keywords_zh: [],
    app_type: 'web',
    target_scenario: 'test scenario',
  },
  source_results: [],
  competitors: [],
  market_summary: 'summary',
  go_no_go: 'go',
  recommendation_type: 'go',
  differentiation_angles: [],
  confidence: {
    sample_size: 0,
    source_coverage: 0,
    source_success_rate: 0,
    freshness_hint: 'Generated moments ago',
    score: 0,
  },
  evidence_summary: {
    top_evidence: [],
    evidence_items: [],
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
  },
  created_at: new Date().toISOString(),
}

function buildReport(overrides: Partial<ResearchReport> = {}): ResearchReport {
  return {
    ...BASE_REPORT,
    ...overrides,
    intent: {
      ...BASE_REPORT.intent,
      ...(overrides.intent ?? {}),
    },
    confidence: {
      ...BASE_REPORT.confidence,
      ...(overrides.confidence ?? {}),
    },
    evidence_summary: {
      ...BASE_REPORT.evidence_summary,
      ...(overrides.evidence_summary ?? {}),
    },
    cost_breakdown: {
      ...BASE_REPORT.cost_breakdown,
      ...(overrides.cost_breakdown ?? {}),
    },
    report_meta: {
      ...BASE_REPORT.report_meta,
      llm_fault_tolerance: {
        ...BASE_REPORT.report_meta.llm_fault_tolerance,
        ...(overrides.report_meta?.llm_fault_tolerance ?? {}),
      },
    },
  }
}

describe('ReportPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getReportRuntimeStatus).mockResolvedValue({
      status: 'not_found',
      report_id: 'default-report',
      message: 'Report not found or expired. Please start a new analysis.',
    })
    vi.mocked(useSSE).mockReturnValue({
      events: [],
      isComplete: false,
      isReconnecting: false,
      error: null,
      cancelled: null,
      retry: vi.fn(),
    })
  })

  it('renders completed report immediately without waiting for SSE completion', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: buildReport({
        id: 'r1',
        query: 'Completed report query',
      }),
    })

    render(
      <MemoryRouter initialEntries={['/reports/r1']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('HEADER:Completed report query')).toBeInTheDocument()
    })

    expect(screen.queryByText('STEPPER')).not.toBeInTheDocument()
    expect(screen.getByText('HERO')).toBeInTheDocument()
    expect(screen.getByText('CONFIDENCE')).toBeInTheDocument()
    expect(screen.getByText('EVIDENCE_COST')).toBeInTheDocument()
  })

  it('does not treat degraded sources as all-failed', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: buildReport({
        id: 'r2',
        query: 'Degraded source report',
        source_results: [
          {
            platform: 'github',
            status: 'degraded',
            raw_count: 0,
            competitors: [],
            error_msg: 'timeout',
            duration_ms: 1000,
          },
        ],
        differentiation_angles: ['angle'],
      }),
    })

    render(
      <MemoryRouter initialEntries={['/reports/r2']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('HEADER:Degraded source report')).toBeInTheDocument()
    })

    expect(screen.queryByText('Couldn\'t reach data sources')).not.toBeInTheDocument()
    expect(screen.getByText('HERO')).toBeInTheDocument()
  })

  it('uses a broadened query when retrying blue-ocean analysis', async () => {
    const broadenButtonLabel = i18n.t('report.blueOcean.tryBroader')
    vi.mocked(startAnalysis).mockResolvedValue({ report_id: 'r-next' })
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: buildReport({
        id: 'r3',
        query: 'Niche AI notebook for legal teams',
        source_results: [
          {
            platform: 'github',
            status: 'ok',
            raw_count: 1,
            competitors: [],
            error_msg: null,
            duration_ms: 100,
          },
        ],
        differentiation_angles: ['angle'],
      }),
    })

    render(
      <MemoryRouter initialEntries={['/reports/r3']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(broadenButtonLabel)).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText(broadenButtonLabel))
    await waitFor(() => {
      expect(startAnalysis).toHaveBeenCalledTimes(1)
    })

    const calledQuery = vi.mocked(startAnalysis).mock.calls[0][0]
    expect(calledQuery).not.toBe('Niche AI notebook for legal teams')
  })

  it('shows chart fallback before loading landscape visualization', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: buildReport({
        id: 'r4',
        query: 'Visualization query',
        source_results: [
          {
            platform: 'github',
            status: 'ok',
            raw_count: 2,
            competitors: [],
            error_msg: null,
            duration_ms: 100,
          },
        ],
        competitors: [
          {
            name: 'Comp A',
            links: ['https://example.com'],
            one_liner: 'desc',
            features: [],
            pricing: null,
            strengths: [],
            weaknesses: [],
            relevance_score: 0.8,
            source_urls: ['https://example.com'],
            source_platforms: ['github'],
          },
        ],
        differentiation_angles: ['angle'],
      }),
    })

    render(
      <MemoryRouter initialEntries={['/reports/r4']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('HEADER:Visualization query')).toBeInTheDocument()
    })
    expect(screen.getByTestId('chart-loading')).toBeInTheDocument()
    expect(await screen.findByText('CHART')).toBeInTheDocument()
  })

  it('shows error banner without progress pane when stream errors', async () => {
    vi.mocked(useSSE).mockReturnValue({
      events: [],
      isComplete: true,
      isReconnecting: false,
      error: 'Connection lost',
      cancelled: null,
      retry: vi.fn(),
    })
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'processing',
    })

    render(
      <MemoryRouter initialEntries={['/reports/r5']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Connection lost')).toBeInTheDocument()
    })
    expect(screen.queryByText('STEPPER')).not.toBeInTheDocument()
  })

  it('shows missing-report guidance when report is not found', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({ status: 'missing' })
    vi.mocked(getReportRuntimeStatus).mockResolvedValue({
      status: 'not_found',
      report_id: 'r-missing',
      message: 'Report not found or expired. Please start a new analysis.',
    })

    render(
      <MemoryRouter initialEntries={['/reports/r-missing']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByText('Report not found or expired. Please start a new analysis.'),
      ).toBeInTheDocument()
    })
    expect(screen.queryByText('STEPPER')).not.toBeInTheDocument()
  })

  it('prevents duplicate broaden submissions while request is pending', async () => {
    const broadenButtonLabel = i18n.t('report.blueOcean.tryBroader')
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: buildReport({
        id: 'r6',
        query: 'Niche AI notebook for legal teams',
        source_results: [
          {
            platform: 'github',
            status: 'ok',
            raw_count: 1,
            competitors: [],
            error_msg: null,
            duration_ms: 100,
          },
        ],
        differentiation_angles: ['angle'],
      }),
    })
    vi.mocked(startAnalysis).mockImplementation(
      () => new Promise(() => {}),
    )

    render(
      <MemoryRouter initialEntries={['/reports/r6']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    const broadenButton = await screen.findByRole('button', { name: broadenButtonLabel })
    fireEvent.click(broadenButton)
    fireEvent.click(broadenButton)

    expect(startAnalysis).toHaveBeenCalledTimes(1)
    expect(broadenButton).toBeDisabled()
  })

  it('shows quota warning without upgrade entry when limit is exceeded', async () => {
    vi.mocked(startAnalysis).mockRejectedValue(
      new ApiError('Analysis failed: limit reached', 429, 'QUOTA_EXCEEDED'),
    )

    render(
      <MemoryRouter initialEntries={[{ pathname: '/reports/new', state: { query: 'test idea' } }]}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/daily analysis limit/i)).toBeInTheDocument()
    })
    expect(screen.queryByRole('link', { name: /upgrade/i })).not.toBeInTheDocument()
  })
})
