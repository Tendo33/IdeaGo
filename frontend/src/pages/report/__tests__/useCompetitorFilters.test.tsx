import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { getCompetitorId } from '../../../competitor'
import { useCompetitorFilters } from '../useCompetitorFilters'
import type { ResearchReport } from '../../../types/research'

const report: ResearchReport = {
  id: 'report-1',
  query: 'query',
  intent: {
    keywords_en: ['idea'],
    keywords_zh: [],
    app_type: 'web',
    target_scenario: 'testing',
  },
  source_results: [],
  competitors: [
    {
      name: 'Beta',
      links: [],
      one_liner: 'beta',
      features: [],
      pricing: null,
      strengths: [],
      weaknesses: [],
      relevance_score: 0.5,
      source_platforms: ['tavily'],
      source_urls: [],
    },
    {
      name: 'Alpha',
      links: [],
      one_liner: 'alpha',
      features: [],
      pricing: null,
      strengths: [],
      weaknesses: [],
      relevance_score: 0.9,
      source_platforms: ['github'],
      source_urls: [],
    },
    {
      name: 'Gamma',
      links: [],
      one_liner: 'gamma',
      features: [],
      pricing: null,
      strengths: [],
      weaknesses: [],
      relevance_score: 0.2,
      source_platforms: ['hackernews'],
      source_urls: [],
    },
  ],
  market_summary: '',
  go_no_go: '',
  recommendation_type: 'go',
  differentiation_angles: [],
  created_at: new Date().toISOString(),
}

describe('useCompetitorFilters', () => {
  it('filters by platform and supports sort changes', () => {
    const { result } = renderHook(() => useCompetitorFilters(report))

    expect(result.current.filteredCompetitors.map(c => c.name)).toEqual(['Alpha', 'Beta', 'Gamma'])

    act(() => {
      result.current.togglePlatform('github')
    })
    expect(result.current.filteredCompetitors.map(c => c.name)).toEqual(['Alpha'])

    act(() => {
      result.current.togglePlatform('github')
      result.current.setSortBy('name')
    })
    expect(result.current.filteredCompetitors.map(c => c.name)).toEqual(['Alpha', 'Beta', 'Gamma'])
  })

  it('tracks compare selection by stable competitor id', () => {
    const duplicateNameReport: ResearchReport = {
      ...report,
      competitors: [
        {
          ...report.competitors[0],
          name: 'Duplicate',
          source_urls: ['https://a.example.com'],
          links: ['https://a.example.com'],
        },
        {
          ...report.competitors[1],
          name: 'Duplicate',
          source_urls: ['https://b.example.com'],
          links: ['https://b.example.com'],
        },
      ],
    }

    const { result } = renderHook(() => useCompetitorFilters(duplicateNameReport))
    const firstId = getCompetitorId(duplicateNameReport.competitors[0])
    const secondId = getCompetitorId(duplicateNameReport.competitors[1])

    act(() => {
      result.current.toggleCompare(firstId)
    })
    expect(result.current.compareCompetitors).toHaveLength(1)

    act(() => {
      result.current.toggleCompare(secondId)
    })
    expect(result.current.compareCompetitors).toHaveLength(2)
  })
})
