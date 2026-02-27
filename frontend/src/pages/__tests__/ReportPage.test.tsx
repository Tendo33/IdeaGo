import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ReportPage } from '../ReportPage'
import { getReportWithStatus, startAnalysis } from '../../api/client'
import { useSSE } from '../../api/useSSE'

vi.mock('../../api/client', () => ({
  getReportWithStatus: vi.fn(),
  cancelAnalysis: vi.fn(),
  startAnalysis: vi.fn(),
}))

vi.mock('../../api/useSSE', () => ({
  useSSE: vi.fn(),
}))

vi.mock('../../components/HorizontalStepper', () => ({ HorizontalStepper: () => <div>STEPPER</div> }))
vi.mock('../../components/ReportHeader', () => ({
  ReportHeader: ({ report }: { report: { query: string } }) => <div>{`HEADER:${report.query}`}</div>,
}))
vi.mock('../../components/HeroPanel', () => ({ HeroPanel: () => <div>HERO</div> }))
vi.mock('../../components/MarketOverview', () => ({ MarketOverview: () => <div>MARKET</div> }))
vi.mock('../../components/CompetitorCard', () => ({ CompetitorCard: () => <div>CARD</div> }))
vi.mock('../../components/CompetitorRow', () => ({ CompetitorRow: () => <div>ROW</div> }))
vi.mock('../../components/LandscapeChart', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return { LandscapeChart: () => <div>CHART</div> }
})
vi.mock('../../components/InsightCard', () => ({ InsightsSection: () => <div>INSIGHTS</div> }))
vi.mock('../../components/ComparePanel', () => ({
  ComparePanel: () => <div>COMPARE</div>,
  CompareFloatingBar: () => <div>FLOATING</div>,
}))
vi.mock('../../components/SectionNav', () => ({ SectionNav: () => <div>NAV</div> }))
vi.mock('../../components/Skeleton', () => ({
  Skeleton: () => <div>SKELETON</div>,
  CompetitorCardSkeleton: () => <div>CARD-SKELETON</div>,
}))

describe('ReportPage', () => {
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

  it('renders completed report immediately without waiting for SSE completion', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: {
        id: 'r1',
        query: 'Completed report query',
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
        created_at: new Date().toISOString(),
      },
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
  })

  it('does not treat degraded sources as all-failed', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: {
        id: 'r2',
        query: 'Degraded source report',
        intent: {
          keywords_en: ['idea'],
          keywords_zh: [],
          app_type: 'web',
          target_scenario: 'test scenario',
        },
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
        competitors: [],
        market_summary: 'summary',
        go_no_go: 'go',
        recommendation_type: 'go',
        differentiation_angles: ['angle'],
        created_at: new Date().toISOString(),
      },
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
    vi.mocked(startAnalysis).mockResolvedValue({ report_id: 'r-next' })
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: {
        id: 'r3',
        query: 'Niche AI notebook for legal teams',
        intent: {
          keywords_en: ['idea'],
          keywords_zh: [],
          app_type: 'web',
          target_scenario: 'test scenario',
        },
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
        competitors: [],
        market_summary: 'summary',
        go_no_go: 'go',
        recommendation_type: 'go',
        differentiation_angles: ['angle'],
        created_at: new Date().toISOString(),
      },
    })

    render(
      <MemoryRouter initialEntries={['/reports/r3']}>
        <Routes>
          <Route path="/reports/:id" element={<ReportPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Try with broader keywords')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Try with broader keywords'))
    await waitFor(() => {
      expect(startAnalysis).toHaveBeenCalledTimes(1)
    })

    const calledQuery = vi.mocked(startAnalysis).mock.calls[0][0]
    expect(calledQuery).not.toBe('Niche AI notebook for legal teams')
  })

  it('shows chart fallback before loading landscape visualization', async () => {
    vi.mocked(getReportWithStatus).mockResolvedValue({
      status: 'ready',
      report: {
        id: 'r4',
        query: 'Visualization query',
        intent: {
          keywords_en: ['idea'],
          keywords_zh: [],
          app_type: 'web',
          target_scenario: 'test scenario',
        },
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
        market_summary: 'summary',
        go_no_go: 'go',
        recommendation_type: 'go',
        differentiation_angles: ['angle'],
        created_at: new Date().toISOString(),
      },
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
})
