import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ReportCompetitorSection } from '@/features/reports/components/ReportCompetitorSection'
import type { Competitor } from '@/lib/types/research'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) => {
      if (key === 'report.competitors.title') {
        return `Analyzed Competitors (${options?.count}/${options?.total})`
      }
      if (key === 'report.competitors.virtualizedHint') {
        return 'Virtualized list enabled'
      }
      if (key === 'report.sort.label') {
        return 'Sort by'
      }
      if (key.startsWith('report.sort.')) {
        return key
      }
      return key
    },
  }),
}))

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  },
  useReducedMotion: () => true,
}))

vi.mock('@/features/reports/components/VirtualizedCompetitorList', () => ({
  VirtualizedCompetitorList: ({ viewMode }: { viewMode: 'grid' | 'list' }) => (
    <div data-testid={`virtualized-${viewMode}`}>{viewMode}</div>
  ),
}))

vi.mock('@/features/reports/components/CompetitorRow', () => ({
  CompetitorRow: ({ competitor }: { competitor: Competitor }) => (
    <div data-testid="competitor-row">{competitor.name}</div>
  ),
}))

vi.mock('@/features/reports/components/CompetitorCard', () => ({
  CompetitorCard: ({ competitor }: { competitor: Competitor }) => (
    <div data-testid="competitor-card">{competitor.name}</div>
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
    relevance_score: 1 - index / Math.max(count, 1),
    source_platforms: ['github'],
    source_urls: [`https://example-${index + 1}.com`],
  }))
}

describe('ReportCompetitorSection', () => {
  it('keeps virtualization enabled for large list views', () => {
    const competitors = createCompetitors(40)
    const competitorRankById = new Map(
      competitors.map((competitor, index) => [competitor.source_urls[0], index + 1]),
    )

    render(
      <ReportCompetitorSection
        allCompetitors={competitors}
        filteredCompetitors={competitors}
        compareSet={new Set()}
        sortBy="relevance"
        setSortBy={vi.fn()}
        platformFilter={new Set()}
        togglePlatform={vi.fn()}
        viewMode="list"
        setViewMode={vi.fn()}
        toggleCompare={vi.fn()}
        competitorRankById={competitorRankById}
      />,
    )

    expect(screen.getByTestId('virtualized-list')).toBeInTheDocument()
    expect(screen.queryByTestId('competitor-row')).not.toBeInTheDocument()
    expect(screen.getByText('Virtualized list enabled')).toBeInTheDocument()
  })
})
