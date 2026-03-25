import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ReportProgressPane } from '../ReportProgressPane'
import type { PipelineEvent } from '@/lib/types/research'

vi.mock('@/features/reports/components/HorizontalStepper', () => ({
  HorizontalStepper: () => <div>STEPPER</div>,
}))

describe('ReportProgressPane', () => {
  it('renders the idea profile when sanitized intent data keeps keywords or target scenario without app type', () => {
    const events: PipelineEvent[] = [
      {
        type: 'intent_parsed',
        stage: 'intent',
        message: 'Intent parsed',
        data: {
          keywords: ['legal', 'assistant'],
          target_scenario: 'contract review',
        },
        timestamp: '2026-02-24T18:00:00.000Z',
      },
    ]

    render(
      <ReportProgressPane
        show
        events={events}
        isReconnecting={false}
        loadPhase="processing"
        isComplete={false}
        reportId="r-progress"
        onCancel={() => {}}
      />,
    )

    expect(screen.getByText('STEPPER')).toBeInTheDocument()
    expect(screen.getByText('legal')).toBeInTheDocument()
    expect(screen.getByText('assistant')).toBeInTheDocument()
    expect(screen.getByText('contract review')).toBeInTheDocument()
  })

  it('falls back to stage-derived source names and safe counts when progress data is missing', () => {
    const events: PipelineEvent[] = [
      {
        type: 'source_completed',
        stage: 'reddit_search',
        message: 'Source completed',
        data: {},
        timestamp: '2026-02-24T18:00:00.000Z',
      },
      {
        type: 'extraction_completed',
        stage: 'extract',
        message: 'Extraction completed',
        data: {},
        timestamp: '2026-02-24T18:00:01.000Z',
      },
    ]

    render(
      <ReportProgressPane
        show
        events={events}
        isReconnecting={false}
        loadPhase="processing"
        isComplete={false}
        reportId="r-progress"
        onCancel={() => {}}
      />,
    )

    expect(screen.getByText('STEPPER')).toBeInTheDocument()
    expect(screen.getAllByText(/reddit/i).length).toBeGreaterThan(0)
    expect(screen.getAllByText('0').length).toBeGreaterThan(0)
  })
})
