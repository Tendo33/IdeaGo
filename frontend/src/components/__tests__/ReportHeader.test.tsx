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
})
