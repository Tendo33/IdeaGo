import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Competitor } from '../../types/research'
import { VirtualizedCompetitorList } from '../VirtualizedCompetitorList'

vi.mock('../CompetitorRow', () => ({
  CompetitorRow: ({ competitor, rank }: { competitor: Competitor; rank: number }) => (
    <div data-testid="virtual-row">{`${rank}:${competitor.name}`}</div>
  ),
}))

vi.mock('../CompetitorCard', () => ({
  CompetitorCard: ({ competitor, rank }: { competitor: Competitor; rank: number }) => (
    <div data-testid="virtual-card">{`${rank}:${competitor.name}`}</div>
  ),
}))

function createCompetitors(count: number): Competitor[] {
  return Array.from({ length: count }, (_, index) => ({
    name: `Competitor ${index + 1}`,
    links: [`https://example-${index + 1}.com`],
    one_liner: 'desc',
    features: [],
    pricing: null,
    strengths: [],
    weaknesses: [],
    relevance_score: 0.5,
    source_platforms: ['github'],
    source_urls: [`https://example-${index + 1}.com`],
  }))
}

describe('VirtualizedCompetitorList', () => {
  beforeEach(() => {
    if (typeof ResizeObserver === 'undefined') {
      vi.stubGlobal(
        'ResizeObserver',
        class {
          observe() {}
          disconnect() {}
        },
      )
    }
  })

  it('renders only a windowed subset for long list mode', () => {
    const competitors = createCompetitors(100)

    render(
      <VirtualizedCompetitorList
        competitors={competitors}
        viewMode="list"
        compareSet={new Set()}
        onToggleCompare={vi.fn()}
      />,
    )

    const renderedRows = screen.getAllByTestId('virtual-row')
    expect(renderedRows.length).toBeGreaterThan(0)
    expect(renderedRows.length).toBeLessThan(40)
    expect(screen.queryByText('100:Competitor 100')).not.toBeInTheDocument()
  })

  it('resets scroll position when view mode changes', () => {
    const competitors = createCompetitors(80)
    const { container, rerender } = render(
      <VirtualizedCompetitorList
        competitors={competitors}
        viewMode="list"
        compareSet={new Set()}
        onToggleCompare={vi.fn()}
      />,
    )

    const scroller = container.firstChild as HTMLElement
    scroller.scrollTop = 480
    fireEvent.scroll(scroller)
    expect(scroller.scrollTop).toBe(480)

    rerender(
      <VirtualizedCompetitorList
        competitors={competitors}
        viewMode="grid"
        compareSet={new Set()}
        onToggleCompare={vi.fn()}
      />,
    )

    expect(scroller.scrollTop).toBe(0)
  })

  it('resets scroll position when competitor identity changes', () => {
    const competitors = createCompetitors(80)
    const { container, rerender } = render(
      <VirtualizedCompetitorList
        competitors={competitors}
        viewMode="list"
        compareSet={new Set()}
        onToggleCompare={vi.fn()}
      />,
    )

    const scroller = container.firstChild as HTMLElement
    scroller.scrollTop = 300
    fireEvent.scroll(scroller)
    expect(scroller.scrollTop).toBe(300)

    const updatedCompetitors = [...competitors]
    updatedCompetitors[0] = {
      ...updatedCompetitors[0],
      source_urls: ['https://changed-source.example.com'],
      links: ['https://changed-source.example.com'],
    }

    rerender(
      <VirtualizedCompetitorList
        competitors={updatedCompetitors}
        viewMode="list"
        compareSet={new Set()}
        onToggleCompare={vi.fn()}
      />,
    )

    expect(scroller.scrollTop).toBe(0)
  })

  it('uses a single-column grid class when virtual columns collapse to one', () => {
    const competitors = createCompetitors(8)
    const { container } = render(
      <VirtualizedCompetitorList
        competitors={competitors}
        viewMode="grid"
        compareSet={new Set()}
        onToggleCompare={vi.fn()}
      />,
    )

    const rowGrid = container.querySelector('div.grid')
    expect(rowGrid).not.toBeNull()
    expect(rowGrid?.className).toContain('grid-cols-1')
    expect(rowGrid?.className).not.toContain('lg:grid-cols-2')
  })
})
