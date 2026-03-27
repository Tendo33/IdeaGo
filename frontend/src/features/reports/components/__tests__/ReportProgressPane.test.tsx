import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ReportProgressPane } from '../ReportProgressPane'
import { deriveProgressModel } from '../progressModel'
import type { PipelineEvent } from '@/lib/types/research'
import i18n from '@/lib/i18n/i18n'

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

  it('adds a dedicated query planning stage between intent and source fetching', () => {
    const events: PipelineEvent[] = [
      {
        type: 'intent_parsed',
        stage: 'intent',
        message: 'Intent parsed',
        data: {
          keywords: ['video', 'ads'],
        },
        timestamp: '2026-03-27T13:20:46.000Z',
      },
      {
        type: 'query_planning_started',
        stage: 'query_planning',
        message: 'Planning queries',
        data: {},
        timestamp: '2026-03-27T13:20:47.000Z',
      },
      {
        type: 'query_planning_completed',
        stage: 'query_planning',
        message: 'Planned queries',
        data: {},
        timestamp: '2026-03-27T13:20:48.000Z',
      },
      {
        type: 'source_started',
        stage: 'github_search',
        message: 'Searching github',
        data: { platform: 'github' },
        timestamp: '2026-03-27T13:20:49.000Z',
      },
    ]

    const model = deriveProgressModel(events, i18n.t.bind(i18n))
    const planningStep = model.steps.find(step => step.id === 'planning')

    expect(planningStep).toBeDefined()
    expect(planningStep?.status).toBe('done')
    expect(model.steps.findIndex(step => step.id === 'planning')).toBe(
      model.steps.findIndex(step => step.id === 'intent') + 1,
    )
  })
})
