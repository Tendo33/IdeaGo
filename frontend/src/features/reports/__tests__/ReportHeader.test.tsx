import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ReportHeader } from '@/features/reports/components/ReportHeader'
import i18n from '@/lib/i18n/i18n'
import type { ResearchReport } from '@/lib/types/research'

const report: ResearchReport = {
  id: 'r1',
  query: 'A startup idea for testing',
  intent: {
    keywords_en: ['startup', 'testing'],
    keywords_zh: [],
    app_type: 'web',
    target_scenario: 'test scenario',
    output_language: 'en',
    search_queries: [],
    cache_key: 'report-header',
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
  go_no_go: '',
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
      endpoints_tried: [],
      last_error_class: '',
    },
    quality_warnings: [],
  },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

describe('ReportHeader dropdown accessibility', () => {
  beforeEach(() => {
    void i18n.changeLanguage('en')
    vi.stubGlobal('navigator', {
      ...navigator,
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  it('exposes expanded state and closes on Escape', async () => {
    render(
      <MemoryRouter>
        <ReportHeader report={report} />
      </MemoryRouter>,
    )

    const shareButton = screen.getByRole('button', { name: /share/i })
    fireEvent.click(shareButton)

    expect(shareButton).toHaveAttribute('aria-expanded', 'true')
    const menu = screen.getByRole('menu')
    expect(menu).toBeInTheDocument()
    expect(menu.className).not.toContain('backdrop-blur')

    fireEvent.keyDown(document, { key: 'Escape' })

    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })
    expect(shareButton).toHaveAttribute('aria-expanded', 'false')
  })

  it('shows fallback message when clipboard write fails', async () => {
    vi.stubGlobal('navigator', {
      ...navigator,
      clipboard: {
        writeText: vi.fn().mockRejectedValue(new Error('clipboard denied')),
      },
    })

    render(
      <MemoryRouter>
        <ReportHeader report={report} />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: /share/i }))
    fireEvent.click(screen.getByRole('menuitem', { name: /copy report link/i }))

    await waitFor(() => {
      expect(screen.getByText("We couldn't copy the link. Please copy it manually from your address bar.")).toBeInTheDocument()
    })
  })

  it('supports arrow-key navigation and closes on Escape', async () => {
    render(
      <MemoryRouter>
        <ReportHeader report={report} />
      </MemoryRouter>,
    )

    const exportButton = screen.getByRole('button', { name: /export/i })
    fireEvent.click(exportButton)

    const menuItems = screen.getAllByRole('menuitem')
    expect(menuItems.length).toBeGreaterThan(1)
    expect(menuItems[0]).toHaveFocus()

    fireEvent.keyDown(menuItems[0], { key: 'ArrowDown' })
    expect(menuItems[1]).toHaveFocus()

    fireEvent.keyDown(menuItems[1], { key: 'ArrowUp' })
    expect(menuItems[0]).toHaveFocus()

    fireEvent.keyDown(menuItems[0], { key: 'Escape' })
    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })
    expect(exportButton).toHaveFocus()
  })

  it('prefers english keywords in english UI even if output language is zh', async () => {
    await i18n.changeLanguage('en')
    const reportWithBothKeywordLists: ResearchReport = {
      ...report,
      intent: {
        ...report.intent,
        keywords_en: ['english-keyword', 'market-fit'],
        keywords_zh: ['中文关键词', '市场契合'],
        output_language: 'zh',
      },
    }

    render(
      <MemoryRouter>
        <ReportHeader report={reportWithBothKeywordLists} />
      </MemoryRouter>,
    )

    expect(screen.getByText('english-keyword, market-fit')).toBeInTheDocument()
    expect(screen.queryByText('中文关键词, 市场契合')).not.toBeInTheDocument()
  })
})
