import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, Gauge, ReceiptText } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { CostBreakdown, EvidenceSummary, ReportMeta } from '../types/research'

interface EvidenceCostCardProps {
  evidenceSummary: EvidenceSummary | null | undefined
  costBreakdown: CostBreakdown | null | undefined
  reportMeta: ReportMeta | null | undefined
}

export function EvidenceCostCard({
  evidenceSummary,
  costBreakdown,
  reportMeta,
}: EvidenceCostCardProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const hasPayload = Boolean(evidenceSummary && costBreakdown && reportMeta)

  const topEvidence = Array.isArray(evidenceSummary?.top_evidence)
    ? evidenceSummary.top_evidence
    : []
  const evidenceItems = Array.isArray(evidenceSummary?.evidence_items)
    ? evidenceSummary.evidence_items
    : []

  const endpointMeta = reportMeta?.llm_fault_tolerance ?? {
    fallback_used: false,
    endpoints_tried: [],
    last_error_class: '',
  }
  const llmCalls = toNonNegativeInt(costBreakdown?.llm_calls)
  const retries = toNonNegativeInt(costBreakdown?.llm_retries)
  const failovers = toNonNegativeInt(costBreakdown?.endpoint_failovers)
  const latencySeconds = Math.round(toNonNegativeInt(costBreakdown?.pipeline_latency_ms) / 1000)

  return (
    <div className="card">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="text-sm font-semibold font-heading text-text inline-flex items-center gap-2">
          <ReceiptText className="w-4 h-4 text-cta" />
          {t('report.transparency.evidence.title')}
        </h3>
        <button
          onClick={() => setExpanded(prev => !prev)}
          className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-cta transition-colors cursor-pointer"
        >
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          {expanded ? t('report.hero.showLess') : t('report.hero.readMore')}
        </button>
      </div>

      <div className="space-y-2 mb-4">
        {topEvidence.length > 0 ? topEvidence.slice(0, 3).map((item, index) => (
          <div key={index} className="text-xs text-text-muted rounded-md bg-muted/55 border border-border/80 px-2.5 py-2">
            {item}
          </div>
        )) : (
          <p className="text-xs text-text-dim">{t('report.transparency.evidence.empty')}</p>
        )}
      </div>

      {expanded && (
        <div className="space-y-2 mb-4">
          {evidenceItems.slice(0, 6).map((item, index) => (
            <div key={`${item.title}-${index}`} className="rounded-md border border-border/80 bg-muted/55 px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-text truncate">{item.title || t('report.transparency.evidence.unknown')}</p>
                  <p className="text-[11px] text-text-dim mt-0.5">{item.platform}</p>
                  <p className="text-xs text-text-muted mt-1 line-clamp-2">{item.snippet}</p>
                </div>
                {item.url ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-cta hover:text-cta-hover shrink-0"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    {t('report.transparency.evidence.viewSource')}
                  </a>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="pt-3 border-t border-border">
        <h4 className="text-xs font-medium text-text mb-2 inline-flex items-center gap-1.5">
          <Gauge className="w-3.5 h-3.5 text-cta" />
          {t('report.transparency.cost.title')}
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <CostMetric label={t('report.transparency.cost.llmCalls')} value={llmCalls} />
          <CostMetric label={t('report.transparency.cost.retries')} value={retries} />
          <CostMetric label={t('report.transparency.cost.failovers')} value={failovers} />
          <CostMetric label={t('report.transparency.cost.latency')} value={`${latencySeconds}s`} />
        </div>
        <p className="mt-2 text-[11px] text-text-dim">
          {t('report.transparency.cost.meta', {
            fallbackUsed: endpointMeta.fallback_used ? t('report.transparency.cost.yes') : t('report.transparency.cost.no'),
            endpoints: endpointMeta.endpoints_tried.join(', ') || '-',
            errorClass: endpointMeta.last_error_class || '-',
          })}
        </p>
        {!hasPayload && (
          <p className="mt-2 text-xs text-warning">{t('report.transparency.unavailable')}</p>
        )}
      </div>
    </div>
  )
}

function CostMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-border/80 bg-muted/55 px-2.5 py-2">
      <p className="text-[11px] text-text-dim">{label}</p>
      <p className="text-xs font-semibold text-text mt-0.5">{value}</p>
    </div>
  )
}

function toNonNegativeInt(value: number | undefined): number {
  const normalized = Number(value)
  if (!Number.isFinite(normalized)) {
    return 0
  }
  return Math.max(0, Math.round(normalized))
}
