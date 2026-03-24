import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi, afterEach } from 'vitest'
import { HeroPanel } from '@/features/home/components/HeroPanel'
import type { ResearchReport } from '@/lib/types/research'
import i18n from '@/lib/i18n/i18n'

function buildReport(overrides: Partial<ResearchReport> = {}): ResearchReport {
  return {
    id: 'report-1',
    query: 'same-day grocery delivery',
    intent: {
      keywords_en: ['grocery delivery'],
      keywords_zh: ['生鲜配送'],
      app_type: 'marketplace',
      target_scenario: 'local commerce',
      output_language: 'zh',
      search_queries: [],
      cache_key: 'hero-panel',
    },
    source_results: [
      {
        platform: 'github',
        status: 'ok',
        raw_count: 0,
        competitors: [],
        error_msg: null,
        duration_ms: 1000,
      },
    ],
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
    go_no_go: 'Go with caution: 赛道需求明确且区域型玩家证明了本地有机+配送可行，但成功关键在供应稳定、履约成本控制与本地密度。',
    recommendation_type: 'caution',
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
    ...overrides,
  }
}

describe('HeroPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('shows the expand button when the verdict text is visually clamped even if it is under 200 characters', async () => {
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(72)
    vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockReturnValue(144)

    render(<HeroPanel report={buildReport()} />)

    expect(
      await screen.findByRole('button', { name: new RegExp(i18n.t('report.hero.readMore'), 'i') }),
    ).toBeInTheDocument()
  })
})
