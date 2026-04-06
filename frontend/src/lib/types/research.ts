export type Platform =
  | 'github'
  | 'tavily'
  | 'hackernews'
  | 'appstore'
  | 'producthunt'
  | 'reddit'
  | 'google_trends'

export type SourceStatus = 'ok' | 'failed' | 'cached' | 'timeout' | 'degraded'

export type EventType =
  | 'intent_started'
  | 'intent_parsed'
  | 'query_planning_started'
  | 'query_planning_completed'
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

export interface PipelineEventData {
  app_type?: string
  keywords?: string[]
  target_scenario?: string
  platform?: string
  count?: number
  families?: string[]
}

export interface PipelineEvent {
  type: EventType
  stage: string
  message: string
  data: PipelineEventData
  timestamp: string
}

export interface ProgressIntentData {
  appType?: string
  keywords: string[]
  targetScenario?: string
}

export interface ProgressSourceCompletedData {
  platform?: string
  count?: number
}

export interface ProgressExtractionCompletedData {
  count?: number
}

export interface ProgressPlanningCompletedData {
  count?: number
  families: string[]
}

const PIPELINE_EVENT_TYPES: EventType[] = [
  'intent_started',
  'intent_parsed',
  'query_planning_started',
  'query_planning_completed',
  'source_started',
  'source_completed',
  'source_failed',
  'extraction_started',
  'extraction_completed',
  'aggregation_started',
  'aggregation_completed',
  'report_ready',
  'cancelled',
  'error',
]

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isEventType(value: unknown): value is EventType {
  return typeof value === 'string' && PIPELINE_EVENT_TYPES.includes(value as EventType)
}

function readString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined
}

function readStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}

function readCount(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  if (typeof value === 'string' && value.trim().length > 0) {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }
  return undefined
}

export function parseIntentProgressData(raw: unknown): ProgressIntentData {
  if (!isRecord(raw)) {
    return { keywords: [] }
  }

  return {
    appType: readString(raw.app_type),
    keywords: readStringList(raw.keywords),
    targetScenario: readString(raw.target_scenario),
  }
}

export function parseSourceCompletedProgressData(raw: unknown): ProgressSourceCompletedData {
  if (!isRecord(raw)) {
    return {}
  }

  return {
    platform: readString(raw.platform),
    count: readCount(raw.count),
  }
}

export function parseExtractionCompletedProgressData(raw: unknown): ProgressExtractionCompletedData {
  if (!isRecord(raw)) {
    return {}
  }

  return {
    count: readCount(raw.count),
  }
}

export function parsePlanningCompletedProgressData(raw: unknown): ProgressPlanningCompletedData {
  if (!isRecord(raw)) {
    return { families: [] }
  }

  return {
    count: readCount(raw.count),
    families: readStringList(raw.families),
  }
}

export function normalizePipelineEventData(type: EventType, raw: unknown): PipelineEventData {
  if (type === 'intent_parsed') {
    const parsed = parseIntentProgressData(raw)
    return {
      ...(parsed.appType ? { app_type: parsed.appType } : {}),
      ...(parsed.keywords.length > 0 ? { keywords: parsed.keywords } : {}),
      ...(parsed.targetScenario ? { target_scenario: parsed.targetScenario } : {}),
    }
  }

  if (type === 'source_completed') {
    const parsed = parseSourceCompletedProgressData(raw)
    return {
      ...(parsed.platform ? { platform: parsed.platform } : {}),
      ...(parsed.count !== undefined ? { count: parsed.count } : {}),
    }
  }

  if (type === 'query_planning_completed') {
    const parsed = parsePlanningCompletedProgressData(raw)
    return {
      ...(parsed.count !== undefined ? { count: parsed.count } : {}),
      ...(parsed.families.length > 0 ? { families: parsed.families } : {}),
    }
  }

  if (type === 'extraction_completed') {
    const parsed = parseExtractionCompletedProgressData(raw)
    return {
      ...(parsed.count !== undefined ? { count: parsed.count } : {}),
    }
  }

  return {}
}

export function parsePipelineEvent(raw: unknown, fallbackType?: EventType): PipelineEvent | null {
  if (!isRecord(raw)) {
    return null
  }

  const type = isEventType(raw.type) ? raw.type : fallbackType
  if (!type) {
    return null
  }

  return {
    type,
    stage: readString(raw.stage) ?? '',
    message: readString(raw.message) ?? '',
    data: normalizePipelineEventData(type, raw.data),
    timestamp: readString(raw.timestamp) ?? '',
  }
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
  relevance_kind: 'direct' | 'adjacent'
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
  exact_entities: string[]
  comparison_anchors: string[]
  search_goal: string
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
  created_at: string
  updated_at: string
  intent: Intent
  recommendation_type: RecommendationType
  go_no_go: string
  market_summary: string
  pain_signals: PainSignal[]
  commercial_signals: CommercialSignal[]
  whitespace_opportunities: WhitespaceOpportunity[]
  opportunity_score: OpportunityScoreBreakdown
  competitors: Competitor[]
  differentiation_angles: string[]
  evidence_summary: EvidenceSummary
  confidence: ConfidenceMetrics
  source_results: SourceResult[]
  cost_breakdown: CostBreakdown
  report_meta: ReportMeta
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
