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
vi.mock('@/features/reports/components/ConfidenceCard', () => ({ ConfidenceCard: () => <div>CONFIDENCE</div> }))
vi.mock('@/features/reports/components/EvidenceCostCard', () => ({ EvidenceCostCard: () => <div>EVIDENCE_COST</div> }))
vi.mock('@/features/reports/components/MarketOverview', () => ({ MarketOverview: () => <div>MARKET</div> }))
vi.mock('@/features/reports/components/PainSignalsCard', () => ({ PainSignalsCard: () => <div>PAIN_SIGNALS</div> }))
vi.mock('@/features/reports/components/CommercialSignalsCard', () => ({ CommercialSignalsCard: () => <div>COMMERCIAL_SIGNALS</div> }))
vi.mock('@/features/reports/components/WhitespaceOpportunityCard', () => ({
  WhitespaceOpportunityCard: () => <div>WHITESPACE_OPPORTUNITIES</div>,
}))
vi.mock('@/features/reports/components/CompetitorCard', () => ({ CompetitorCard: () => <div>CARD</div> }))
vi.mock('@/features/reports/components/CompetitorRow', () => ({ CompetitorRow: () => <div>ROW</div> }))
vi.mock('@/features/reports/components/LandscapeChart', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return { LandscapeChart: () => <div>CHART</div> }
})
vi.mock('@/features/reports/components/ComparePanel', () => ({
  ComparePanel: () => <div>COMPARE</div>,
  CompareFloatingBar: () => <div>FLOATING</div>,
}))
vi.mock('@/features/reports/components/SectionNav', () => ({
  SectionNav: ({
    sections,
  }: {
    sections: Array<{ id: string }>
  }) => (
    <div data-testid="section-nav-shape">{sections.map(section => section.id).join('|')}</div>
  ),
}))
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
    exact_entities: [],
    comparison_anchors: [],
    search_goal: 'validate',
    app_type: 'web',
    target_scenario: 'test scenario',
    output_language: 'en',
    search_queries: [],
    cache_key: 'base-report',
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
    freshness_hint: 'Generated moments ago',
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

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
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
    expect(screen.getByText('PAIN_SIGNALS')).toBeInTheDocument()
    expect(screen.getByText('COMMERCIAL_SIGNALS')).toBeInTheDocument()
    expect(screen.getByText('WHITESPACE_OPPORTUNITIES')).toBeInTheDocument()
    expect(screen.getByText('CONFIDENCE')).toBeInTheDocument()
    expect(screen.getByText('EVIDENCE_COST')).toBeInTheDocument()
  })

  it('does not show the processing pane while loading an existing report', async () => {
    const pendingReport = deferred<Awaited<ReturnType<typeof getReportWithStatus>>>()
    vi.mocked(getReportWithStatus).mockReturnValueOnce(pendingReport.promise)

    render(
      <MemoryRouter initialEntries={['/reports/r-loading']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.queryByText('STEPPER')).not.toBeInTheDocument()
    expect(screen.queryByText('正在拆解您的想法')).not.toBeInTheDocument()

    pendingReport.resolve({
      status: 'ready',
      report: buildReport({
        id: 'r-loading',
        query: 'Loaded report',
      }),
    })

    await waitFor(() => {
      expect(screen.getByText('HEADER:Loaded report')).toBeInTheDocument()
    })
  })

  it('uses decision-first section nav shape', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: buildReport({
        id: 'r-nav',
        query: 'Decision first nav',
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
            relevance_kind: 'direct',
            source_urls: ['https://example.com'],
            source_platforms: ['github'],
          },
        ],
        differentiation_angles: ['angle'],
      }),
    })

    render(
      <MemoryRouter initialEntries={['/reports/r-nav']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('HEADER:Decision first nav')).toBeInTheDocument()
    })

    expect(await screen.findByTestId('section-nav-shape')).toHaveTextContent(
      'section-should-we-build-this|section-why-now|section-pain|section-commercial|section-whitespace|section-competitors|section-evidence|section-confidence',
    )
  })

  it('omits non-rendered sections from nav shape for sparse reports', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: buildReport({
        id: 'r-sparse',
        query: 'Sparse report',
        market_summary: '',
        competitors: [],
      }),
    })

    render(
      <MemoryRouter initialEntries={['/reports/r-sparse']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('HEADER:Sparse report')).toBeInTheDocument()
    })

    expect(await screen.findByTestId('section-nav-shape')).toHaveTextContent(
      'section-should-we-build-this|section-pain|section-commercial|section-whitespace|section-evidence|section-confidence',
    )
    expect(document.getElementById('section-why-now')).toBeNull()
    expect(document.getElementById('section-competitors')).toBeNull()
  })

  it('renders report sections in decision-first content order', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: buildReport({
        id: 'r-order',
        query: 'Decision first content order',
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
            relevance_kind: 'direct',
            source_urls: ['https://example.com'],
            source_platforms: ['github'],
          },
        ],
        differentiation_angles: ['angle'],
      }),
    })

    render(
      <MemoryRouter initialEntries={['/reports/r-order']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('HEADER:Decision first content order')).toBeInTheDocument()
    })

    const orderedSectionIds = [
      'section-should-we-build-this',
      'section-why-now',
      'section-pain',
      'section-commercial',
      'section-whitespace',
      'section-competitors',
      'section-evidence',
      'section-confidence',
    ]
    const sections = orderedSectionIds.map(id => document.getElementById(id))
    sections.forEach(section => {
      expect(section).not.toBeNull()
    })

    for (let index = 1; index < sections.length; index += 1) {
      const previous = sections[index - 1] as HTMLElement
      const current = sections[index] as HTMLElement
      expect(previous.compareDocumentPosition(current) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0)
    }
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
    expect(screen.getByText('PAIN_SIGNALS')).toBeInTheDocument()
    expect(screen.getByText('COMMERCIAL_SIGNALS')).toBeInTheDocument()
    expect(screen.getByText('WHITESPACE_OPPORTUNITIES')).toBeInTheDocument()
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
            relevance_kind: 'direct',
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
    expect(screen.queryByTestId('chart-loading') ?? screen.getByText('CHART')).toBeInTheDocument()
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
          <Route path="/" element={<div>HOME</div>} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(
        screen.getByText('Report not found or expired. Please start a new analysis.'),
      ).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: i18n.t('error.backToHome') })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: i18n.t('report.failed.startAgain') })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: i18n.t('error.backToHome') }))

    await waitFor(() => {
      expect(screen.getByText('HOME')).toBeInTheDocument()
    })
    expect(screen.queryByText('STEPPER')).not.toBeInTheDocument()
  })

  it('retries failed report creation from /reports/new with the original query', async () => {
    vi.mocked(startAnalysis)
      .mockRejectedValueOnce(new Error('Analysis failed: temporary outage'))
      .mockResolvedValueOnce({ report_id: 'r-created-retry' })
    vi.mocked(getReportWithStatus).mockResolvedValue({ status: 'processing' })

    render(
      <MemoryRouter initialEntries={[{ pathname: '/reports/new', state: { query: 'retryable idea' } }]}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Analysis failed: temporary outage')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: i18n.t('report.failed.retryShort') }))

    await waitFor(() => {
      expect(startAnalysis).toHaveBeenNthCalledWith(1, 'retryable idea', expect.any(Object))
      expect(startAnalysis).toHaveBeenNthCalledWith(2, 'retryable idea', undefined)
    })
  })

  it('restarts analysis when a completed report never becomes available', async () => {
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
        report_id: 'r-complete-missing',
        query: 'AI CRM for recruiters',
      })
      .mockResolvedValueOnce({
        status: 'complete',
        report_id: 'r-complete-missing',
        query: 'AI CRM for recruiters',
      })
      .mockResolvedValueOnce({
        status: 'complete',
        report_id: 'r-complete-missing',
        query: 'AI CRM for recruiters',
      })
    vi.mocked(startAnalysis).mockResolvedValue({ report_id: 'r-regenerated' })

    render(
      <MemoryRouter initialEntries={['/reports/r-complete-missing']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: i18n.t('report.failed.startAgain') })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: i18n.t('report.failed.startAgain') }))

    await waitFor(() => {
      expect(startAnalysis).toHaveBeenCalledWith('AI CRM for recruiters')
    })
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

  it('starts a new analysis from the URL query when /reports/new is refreshed directly', async () => {
    vi.mocked(startAnalysis).mockResolvedValue({ report_id: 'r-url-query' })

    render(
      <MemoryRouter initialEntries={['/reports/new?q=url%20idea']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(startAnalysis).toHaveBeenCalledWith('url idea', expect.any(Object))
    })
  })

  it('prefers the URL query over router state when both are present', async () => {
    vi.mocked(startAnalysis).mockResolvedValue({ report_id: 'r-url-wins' })

    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: '/reports/new',
            search: '?q=url%20idea',
            state: { query: 'state idea' },
          },
        ]}
      >
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(startAnalysis).toHaveBeenCalledWith('url idea', expect.any(Object))
    })
    expect(startAnalysis).not.toHaveBeenCalledWith('state idea', expect.anything())
  })
})
