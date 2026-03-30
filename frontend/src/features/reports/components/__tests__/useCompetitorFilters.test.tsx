import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { getCompetitorId } from '@/features/reports/competitor'
import { useCompetitorFilters } from '../useCompetitorFilters'
import type { ResearchReport } from '@/lib/types/research'

const report: ResearchReport = {
  id: 'report-1',
  query: 'query',
  intent: {
    keywords_en: ['idea'],
    keywords_zh: [],
    exact_entities: [],
    comparison_anchors: [],
    search_goal: 'compare_competitors',
    app_type: 'web',
    target_scenario: 'testing',
    output_language: 'en',
    search_queries: [],
    cache_key: 'competitor-filters',
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
    sample_size: 3,
    source_coverage: 2,
    source_success_rate: 0.8,
    source_diversity: 0,
    evidence_density: 0,
    recency_score: 0,
    degradation_penalty: 0,
    contradiction_penalty: 0,
    reasons: [],
    freshness_hint: 'Generated moments ago',
    score: 74,
  },
  evidence_summary: {
    top_evidence: ['Alpha has strong relevance'],
    evidence_items: [],
    category_counts: {},
    source_platforms: [],
    freshness_distribution: {},
    degraded_sources: [],
    uncertainty_notes: [],
  },
  cost_breakdown: {
    llm_calls: 3,
    llm_retries: 1,
    endpoint_failovers: 0,
    source_calls: 2,
    pipeline_latency_ms: 1200,
    tokens_prompt: 0,
    tokens_completion: 0,
  },
  report_meta: {
    llm_fault_tolerance: {
      fallback_used: false,
      endpoints_tried: ['primary'],
      last_error_class: '',
    },
    quality_warnings: [],
  },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
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

  it('resets filter, view and compare state when report id changes', () => {
    const nextReport: ResearchReport = {
      ...report,
      id: 'report-2',
      competitors: [...report.competitors],
    }

    const { result, rerender } = renderHook(
      ({ currentReport }: { currentReport: ResearchReport }) => useCompetitorFilters(currentReport),
      { initialProps: { currentReport: report } },
    )

    act(() => {
      result.current.togglePlatform('github')
      result.current.setViewMode('list')
      result.current.toggleCompare(getCompetitorId(report.competitors[0]))
      result.current.setShowCompare(true)
    })

    expect(result.current.platformFilter.size).toBe(1)
    expect(result.current.viewMode).toBe('list')
    expect(result.current.compareSet.size).toBe(1)
    expect(result.current.showCompare).toBe(true)

    rerender({ currentReport: nextReport })

    expect(result.current.platformFilter.size).toBe(0)
    expect(result.current.viewMode).toBe('grid')
    expect(result.current.compareSet.size).toBe(0)
    expect(result.current.showCompare).toBe(false)
    expect(result.current.sortBy).toBe('relevance')
  })
})
