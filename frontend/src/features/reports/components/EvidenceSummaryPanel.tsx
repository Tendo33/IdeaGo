import { AlertTriangle, ExternalLink, Layers3, ShieldAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { EvidenceItem, EvidenceSummary } from '@/lib/types/research'

export interface EvidenceSummaryPanelProps {
  evidenceSummary: EvidenceSummary | null | undefined
  expanded?: boolean
}

export function EvidenceSummaryPanel({
  evidenceSummary,
  expanded = false,
}: EvidenceSummaryPanelProps) {
  const { t } = useTranslation()
  const evidenceItems = Array.isArray(evidenceSummary?.evidence_items)
    ? evidenceSummary.evidence_items
    : []
  const visibleItems = expanded ? evidenceItems : evidenceItems.slice(0, 3)
  const categoryEntries = Object.entries(evidenceSummary?.category_counts ?? {}).filter(([, count]) => count > 0)
  const degradedSources = evidenceSummary?.degraded_sources ?? []
  const uncertaintyNotes = evidenceSummary?.uncertainty_notes ?? []
  const topEvidence = evidenceSummary?.top_evidence ?? []
  const freshnessEntries = Object.entries(evidenceSummary?.freshness_distribution ?? {}).filter(([, count]) => count > 0)
  const sourcePlatforms = evidenceSummary?.source_platforms ?? []

  return (
    <div className="space-y-4">
      {topEvidence.length > 0 && (
        <div className="space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
            Evidence highlights
          </p>
          <div className="space-y-2">
            {topEvidence.slice(0, 3).map(item => (
              <div
                key={item}
                className="rounded-none border border-border/70 bg-muted/35 px-3 py-2 text-sm text-foreground"
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      )}

      {(categoryEntries.length > 0 || freshnessEntries.length > 0 || sourcePlatforms.length > 0) && (
        <div className="space-y-3 rounded-none border-2 border-border bg-background p-4">
          <div className="flex items-center gap-2">
            <Layers3 className="h-4 w-4 text-cta" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
              Trust metadata
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {categoryEntries.map(([category, count]) => (
              <TrustPill key={category} label={`${category}: ${count}`} />
            ))}
            {freshnessEntries.map(([bucket, count]) => (
              <TrustPill key={bucket} label={`${bucket}: ${count}`} />
            ))}
            {sourcePlatforms.map(platform => (
              <TrustPill key={platform} label={`platform: ${platform}`} />
            ))}
          </div>
        </div>
      )}

      {(degradedSources.length > 0 || uncertaintyNotes.length > 0) && (
        <div className="space-y-3 rounded-none border-2 border-warning/30 bg-warning/8 p-4">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-warning" />
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
              Trust warnings
            </p>
          </div>
          {degradedSources.length > 0 && (
            <p className="text-sm text-foreground break-words">
              Degraded sources: {degradedSources.join(', ')}
            </p>
          )}
          {uncertaintyNotes.length > 0 && (
            <ul className="space-y-2">
              {uncertaintyNotes.map(note => (
                <li key={note} className="flex items-start gap-2 text-sm text-foreground">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" />
                  <span className="break-words">{note}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="space-y-3">
        {visibleItems.length > 0 ? (
          visibleItems.map((item, index) => (
            <EvidenceItemCard
              key={`${item.title}-${item.url}-${index}`}
              item={item}
              unknownLabel={t('report.transparency.evidence.unknown')}
              viewSourceLabel={t('report.transparency.evidence.viewSource')}
            />
          ))
        ) : (
          <p className="text-xs text-muted-foreground">{t('report.transparency.evidence.empty')}</p>
        )}
      </div>
    </div>
  )
}

interface EvidenceItemCardProps {
  item: EvidenceItem
  unknownLabel: string
  viewSourceLabel: string
}

function EvidenceItemCard({
  item,
  unknownLabel,
  viewSourceLabel,
}: EvidenceItemCardProps) {
  const title = item.title || unknownLabel
  const categoryLabel = item.category || 'market'
  const platformLabel = item.platform || 'unknown'

  return (
    <div className="rounded-none border-2 border-border bg-muted/55 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-xs font-medium text-foreground break-words">{title}</p>
            <span className="rounded-none border border-border/70 bg-background px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {categoryLabel}
            </span>
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            <span>{platformLabel}</span>
            {item.query_family ? <span>family: {item.query_family}</span> : null}
            {item.matched_query ? <span>query: {item.matched_query}</span> : null}
            {item.freshness_hint ? <span>freshness: {item.freshness_hint}</span> : null}
          </div>
          {item.snippet ? (
            <p className="text-xs text-muted-foreground break-words leading-relaxed">{item.snippet}</p>
          ) : null}
        </div>
        {item.url ? (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex shrink-0 items-center gap-1 rounded-none px-1 text-xs text-cta transition-colors hover:text-cta-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            {viewSourceLabel}
          </a>
        ) : null}
      </div>
    </div>
  )
}

interface TrustPillProps {
  label: string
}

function TrustPill({ label }: TrustPillProps) {
  return (
    <span className="rounded-none border border-border/70 bg-muted/35 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
      {label}
    </span>
  )
}
