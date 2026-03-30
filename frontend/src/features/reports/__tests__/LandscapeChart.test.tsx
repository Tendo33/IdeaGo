import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getCompetitorDomId } from '@/features/reports/competitor'
import type { Competitor } from '@/lib/types/research'
import { LandscapeChart } from '@/features/reports/components/LandscapeChart'

let scatterClickPayload: Record<string, unknown> | null = null

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  ScatterChart: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Scatter: ({
    data,
    onClick,
  }: {
    data: Array<Record<string, unknown>>
    onClick?: (entry: Record<string, unknown>) => void
  }) => (
    <button
      type="button"
      data-testid="scatter-dot"
      onClick={() => onClick?.(scatterClickPayload ?? { payload: data[0] })}
    >
      dot
    </button>
  ),
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
  Cell: () => null,
}))

describe('LandscapeChart', () => {
  beforeEach(() => {
    scatterClickPayload = null
  })

  it('scrolls to stable competitor anchor on dot click', () => {
    const competitor: Competitor = {
      name: 'Acme',
      links: ['https://acme.example.com'],
      one_liner: 'Acme description',
      features: ['feature-1'],
      pricing: null,
      strengths: [],
      weaknesses: [],
      relevance_score: 0.81,
      source_platforms: ['github'],
      source_urls: ['https://acme.example.com'],
    }
    const domId = getCompetitorDomId(competitor)
    const scrollIntoView = vi.fn()

    render(
      <>
        <div id={domId} data-testid="target-card" />
        <LandscapeChart competitors={[competitor]} />
      </>,
    )

    const target = screen.getByTestId('target-card')
    Object.defineProperty(target, 'scrollIntoView', {
      value: scrollIntoView,
      configurable: true,
    })

    fireEvent.click(screen.getByTestId('scatter-dot'))

    expect(scrollIntoView).toHaveBeenCalled()
    expect(target.classList.contains('ring-2')).toBe(true)
  })

  it('offers a keyboard-accessible jump action for each competitor', () => {
    const competitor: Competitor = {
      name: 'Acme',
      links: ['https://acme.example.com'],
      one_liner: 'Acme description',
      features: ['feature-1'],
      pricing: null,
      strengths: [],
      weaknesses: [],
      relevance_score: 0.81,
      source_platforms: ['github'],
      source_urls: ['https://acme.example.com'],
    }
    const domId = getCompetitorDomId(competitor)
    const scrollIntoView = vi.fn()

    render(
      <>
        <div id={domId} data-testid="target-card" />
        <LandscapeChart competitors={[competitor]} />
      </>,
    )

    const target = screen.getByTestId('target-card')
    Object.defineProperty(target, 'scrollIntoView', {
      value: scrollIntoView,
      configurable: true,
    })

    fireEvent.click(screen.getByRole('button', { name: 'Jump to competitor Acme' }))

    expect(scrollIntoView).toHaveBeenCalled()
  })

  it('ignores malformed scatter payloads without throwing', () => {
    const competitor: Competitor = {
      name: 'Acme',
      links: ['https://acme.example.com'],
      one_liner: 'Acme description',
      features: ['feature-1'],
      pricing: null,
      strengths: [],
      weaknesses: [],
      relevance_score: 0.81,
      source_platforms: ['github'],
      source_urls: ['https://acme.example.com'],
    }

    scatterClickPayload = { payload: { unexpected: true } }

    render(<LandscapeChart competitors={[competitor]} />)

    expect(() => {
      fireEvent.click(screen.getByTestId('scatter-dot'))
    }).not.toThrow()
  })
})
