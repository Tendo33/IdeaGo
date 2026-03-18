import { useState } from 'react'
import { ChevronDown, ChevronUp, ExternalLink, Gauge, ReceiptText } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { CostBreakdown, EvidenceSummary, ReportMeta } from '@/lib/types/research'

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

  const visibleItems = expanded ? evidenceItems.slice(0, 6) : evidenceItems.slice(0, 3)

  return (
    <div className="card space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold font-heading text-foreground inline-flex items-center gap-2">
          <ReceiptText className="w-4 h-4 text-cta" />
          {t('report.transparency.evidence.title')}
        </h3>
        {evidenceItems.length > 3 && (
          <button
            onClick={() => setExpanded(prev => !prev)}
            className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-cta transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none rounded-none px-1"
          >
            {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {expanded ? t('report.hero.showLess') : t('report.hero.readMore')}
          </button>
        )}
      </div>

      <div className="space-y-3">
        {visibleItems.length > 0 ? (
          visibleItems.map((item, index) => (
            <div key={`${item.title}-${index}`} className="rounded-none border border-2 border-border bg-muted/55 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-foreground truncate" title={item.title || t('report.transparency.evidence.unknown')}>
                    {item.title || t('report.transparency.evidence.unknown')}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{item.platform}</p>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2 break-all">{item.snippet}</p>
                </div>
                {item.url ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-cta hover:text-cta-hover shrink-0 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none rounded-none px-1"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    {t('report.transparency.evidence.viewSource')}
                  </a>
                ) : null}
              </div>
            </div>
          ))
        ) : (
          <p className="text-xs text-muted-foreground">{t('report.transparency.evidence.empty')}</p>
        )}
      </div>

      <div className="pt-5 border-t border-2 border-border">
        <h4 className="text-sm font-bold text-foreground mb-4 inline-flex items-center gap-2">
          <Gauge className="w-4 h-4 text-cta" />
          {t('report.transparency.cost.title')}
        </h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <CostMetric label={t('report.transparency.cost.llmCalls')} value={llmCalls} />
          <CostMetric label={t('report.transparency.cost.retries')} value={retries} />
          <CostMetric label={t('report.transparency.cost.failovers')} value={failovers} />
          <CostMetric label={t('report.transparency.cost.latency')} value={`${latencySeconds}s`} />
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
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
    <div className="rounded-none border border-2 border-border bg-muted/55 p-3 flex flex-col justify-between min-w-0">
      <p className="text-xs text-muted-foreground break-words leading-tight">{label}</p>
      <p className="text-base font-bold text-foreground mt-2 truncate" title={String(value)}>{value}</p>
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
