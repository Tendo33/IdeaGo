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

export interface ConfidenceMetrics {
  sample_size: number
  source_coverage: number
  source_success_rate: number
  freshness_hint: string
  score: number
}

export interface EvidenceItem {
  title: string
  url: string
  platform: string
  snippet: string
}

export interface EvidenceSummary {
  top_evidence: string[]
  evidence_items: EvidenceItem[]
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
}

export interface Intent {
  keywords_en: string[]
  keywords_zh: string[]
  app_type: string
  target_scenario: string
}

export type RecommendationType = 'go' | 'caution' | 'no_go'

export interface ResearchReport {
  id: string
  query: string
  intent: Intent
  source_results: SourceResult[]
  competitors: Competitor[]
  market_summary: string
  go_no_go: string
  recommendation_type: RecommendationType
  differentiation_angles: string[]
  confidence: ConfidenceMetrics
  evidence_summary: EvidenceSummary
  cost_breakdown: CostBreakdown
  report_meta: ReportMeta
  created_at: string
}

export interface ReportListItem {
  id: string
  query: string
  created_at: string
  competitor_count: number
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
