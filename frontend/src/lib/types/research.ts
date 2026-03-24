export type Platform = 'github' | 'tavily' | 'hackernews' | 'appstore' | 'producthunt' | 'reddit' | 'google_trends'

export type SourceStatus = 'ok' | 'failed' | 'cached' | 'timeout' | 'degraded'

export type EventType =
  | 'intent_started'
  | 'intent_parsed'
  | 'source_started'
  | 'source_completed'
  | 'source_failed'
  | 'extraction_started'
  | 'extraction_completed'
  | 'aggregation_started'
  | 'aggregation_completed'
  | 'report_ready'
  | 'cancelled'
  | 'error'

export interface PipelineEvent {
  type: EventType
  stage: string
  message: string
  data: Record<string, unknown>
  timestamp: string
}

export interface Competitor {
  name: string
  links: string[]
  one_liner: string
  features: string[]
  pricing: string | null
  strengths: string[]
  weaknesses: string[]
  relevance_score: number
  source_platforms: Platform[]
  source_urls: string[]
}

export interface SourceResult {
  platform: Platform
  status: SourceStatus
  raw_count: number
  competitors: Competitor[]
  error_msg: string | null
  duration_ms: number
}

export interface SearchQuery {
  platform: Platform
  queries: string[]
}

export interface PainSignal {
  theme: string
  summary: string
  intensity: number
  frequency: number
  evidence_urls: string[]
  source_platforms: Platform[]
}

export interface CommercialSignal {
  theme: string
  summary: string
  intent_strength: number
  monetization_hint: string
  evidence_urls: string[]
  source_platforms: Platform[]
}

export interface WhitespaceOpportunity {
  title: string
  description: string
  target_segment: string
  wedge: string
  potential_score: number
  confidence: number
  supporting_evidence: string[]
}

export interface OpportunityScoreBreakdown {
  pain_intensity: number
  solution_gap: number
  commercial_intent: number
  freshness: number
  competition_density: number
  score: number
}

export interface ConfidenceMetrics {
  sample_size: number
  source_coverage: number
  source_success_rate: number
  source_diversity: number
  evidence_density: number
  recency_score: number
  degradation_penalty: number
  contradiction_penalty: number
  reasons: string[]
  freshness_hint: string
  score: number
}

export type EvidenceCategory =
  | 'competitor'
  | 'pain'
  | 'commercial'
  | 'migration'
  | 'whitespace'
  | 'market'

export interface EvidenceItem {
  title: string
  url: string
  platform: Platform | null
  snippet: string
  category: EvidenceCategory
  freshness_hint: string
  matched_query: string
  query_family: string
}

export interface EvidenceSummary {
  top_evidence: string[]
  evidence_items: EvidenceItem[]
  category_counts: Record<string, number>
  source_platforms: Platform[]
  freshness_distribution: Record<string, number>
  degraded_sources: Platform[]
  uncertainty_notes: string[]
}

export interface CostBreakdown {
  llm_calls: number
  llm_retries: number
  endpoint_failovers: number
  source_calls: number
  pipeline_latency_ms: number
  tokens_prompt: number
  tokens_completion: number
}

export interface LlmFaultToleranceMeta {
  fallback_used: boolean
  endpoints_tried: string[]
  last_error_class: string
}

export interface ReportMeta {
  llm_fault_tolerance: LlmFaultToleranceMeta
  quality_warnings: string[]
}

export interface Intent {
  keywords_en: string[]
  keywords_zh: string[]
  app_type: string
  target_scenario: string
  output_language: string
  search_queries: SearchQuery[]
  cache_key: string
}

export type RecommendationType = 'go' | 'caution' | 'no_go'

export interface ResearchReport {
  id: string
  query: string
  intent: Intent
  source_results: SourceResult[]
  competitors: Competitor[]
  pain_signals: PainSignal[]
  commercial_signals: CommercialSignal[]
  whitespace_opportunities: WhitespaceOpportunity[]
  opportunity_score: OpportunityScoreBreakdown
  market_summary: string
  go_no_go: string
  recommendation_type: RecommendationType
  differentiation_angles: string[]
  confidence: ConfidenceMetrics
  evidence_summary: EvidenceSummary
  cost_breakdown: CostBreakdown
  report_meta: ReportMeta
  created_at: string
  updated_at: string
}

export interface ReportListItem {
  id: string
  query: string
  created_at: string
  competitor_count: number
}

export interface PaginatedReportList {
  items: ReportListItem[]
  total: number
  limit: number | null
  offset: number
}

export type RuntimeStatus =
  | 'processing'
  | 'failed'
  | 'cancelled'
  | 'complete'
  | 'not_found'

export interface ReportRuntimeStatus {
  status: RuntimeStatus
  report_id: string
  error_code?: string | null
  message?: string | null
  updated_at?: string | null
  query?: string | null
}
