import { describe, expect, it } from 'vitest'
import { REPORT_DETAIL_V2_FIELD_ORDER, type ResearchReport } from './research'

describe('ResearchReport contract', () => {
  it('keeps the frontend report-detail field order aligned with the hosted contract', () => {
    const report: ResearchReport = {
      id: 'report-1',
      query: 'AI copilot for operations',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      intent: {
        keywords_en: ['ai', 'copilot'],
        keywords_zh: [],
        exact_entities: [],
        comparison_anchors: [],
        search_goal: 'validate',
        app_type: 'web',
        target_scenario: 'operations',
        output_language: 'en',
        search_queries: [],
        cache_key: 'report-contract',
      },
      recommendation_type: 'go',
      go_no_go: 'Go',
      market_summary: 'Why now',
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
      competitors: [],
      differentiation_angles: [],
      evidence_summary: {
        top_evidence: [],
        evidence_items: [],
        category_counts: {},
        source_platforms: [],
        freshness_distribution: {},
        degraded_sources: [],
        uncertainty_notes: [],
      },
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
        freshness_hint: 'Fresh',
        score: 0,
      },
      source_results: [],
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
    }

    expect(REPORT_DETAIL_V2_FIELD_ORDER).toEqual([
      'id',
      'query',
      'created_at',
      'updated_at',
      'intent',
      'recommendation_type',
      'go_no_go',
      'market_summary',
      'pain_signals',
      'commercial_signals',
      'whitespace_opportunities',
      'opportunity_score',
      'competitors',
      'differentiation_angles',
      'evidence_summary',
      'confidence',
      'source_results',
      'cost_breakdown',
      'report_meta',
    ])
    expect(Object.keys(report)).toEqual(REPORT_DETAIL_V2_FIELD_ORDER)
  })
})
