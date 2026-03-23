import { useState } from 'react'
import { ChevronDown, ExternalLink, ReceiptText } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { EvidenceSummary } from '@/lib/types/research'

interface EvidenceCostCardProps {
  evidenceSummary: EvidenceSummary | null | undefined
}

export function EvidenceCostCard({
  evidenceSummary,
}: EvidenceCostCardProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  const evidenceItems = Array.isArray(evidenceSummary?.evidence_items)
    ? evidenceSummary.evidence_items
    : []

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
            className="inline-flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-cta transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none rounded-none px-1 py-0.5"
          >
            <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-300 ease-out-quint ${expanded ? 'rotate-180' : ''}`} />
            {expanded ? t('report.hero.showLess') : t('report.hero.readMore')}
          </button>
        )}
      </div>

      <div className="space-y-3">
        {visibleItems.length > 0 ? (
          visibleItems.map((item, index) => (
            <div key={`${item.title}-${index}`} className="rounded-none border-2 border-border bg-muted/55 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-foreground truncate" title={item.title || t('report.transparency.evidence.unknown')}>
                    {item.title || t('report.transparency.evidence.unknown')}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5 truncate">{item.platform}</p>
                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2 break-words">{item.snippet}</p>
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
    </div>
  )
}
