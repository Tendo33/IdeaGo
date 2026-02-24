import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ReportPage } from '../ReportPage'
import { getReportWithStatus } from '../../api/client'

vi.mock('../../api/client', () => ({
  getReportWithStatus: vi.fn(),
  cancelAnalysis: vi.fn(),
  startAnalysis: vi.fn(),
}))

vi.mock('../../api/useSSE', () => ({
  useSSE: () => ({
    events: [],
    isComplete: false,
    isReconnecting: false,
    error: null,
    cancelled: null,
    retry: vi.fn(),
  }),
}))

vi.mock('../../components/HorizontalStepper', () => ({ HorizontalStepper: () => <div>STEPPER</div> }))
vi.mock('../../components/ReportHeader', () => ({
  ReportHeader: ({ report }: { report: { query: string } }) => <div>{`HEADER:${report.query}`}</div>,
}))
vi.mock('../../components/HeroPanel', () => ({ HeroPanel: () => <div>HERO</div> }))
vi.mock('../../components/MarketOverview', () => ({ MarketOverview: () => <div>MARKET</div> }))
vi.mock('../../components/CompetitorCard', () => ({ CompetitorCard: () => <div>CARD</div> }))
vi.mock('../../components/CompetitorRow', () => ({ CompetitorRow: () => <div>ROW</div> }))
vi.mock('../../components/LandscapeChart', () => ({ LandscapeChart: () => <div>CHART</div> }))
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
})
