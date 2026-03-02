import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { ReportHeader } from '../ReportHeader'
import type { ResearchReport } from '../../types/research'

const report: ResearchReport = {
  id: 'r1',
  query: 'A startup idea for testing',
  intent: {
    keywords_en: ['startup', 'testing'],
    keywords_zh: [],
    app_type: 'web',
    target_scenario: 'test scenario',
  },
  source_results: [],
  competitors: [],
  market_summary: '',
  go_no_go: '',
  recommendation_type: 'go',
  differentiation_angles: [],
  confidence: {
    sample_size: 0,
    source_coverage: 0,
    source_success_rate: 0,
    freshness_hint: '',
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
      endpoints_tried: [],
      last_error_class: '',
    },
  },
  created_at: new Date().toISOString(),
}

describe('ReportHeader dropdown accessibility', () => {
  beforeEach(() => {
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
    expect(screen.getByRole('menu')).toBeInTheDocument()

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
    fireEvent.click(screen.getByRole('menuitem', { name: /copy link/i }))

    await waitFor(() => {
      expect(screen.getByText('Unable to copy link. Please copy the URL manually.')).toBeInTheDocument()
    })
  })
})
