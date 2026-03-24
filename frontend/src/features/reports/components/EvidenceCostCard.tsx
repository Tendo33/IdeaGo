import { useState } from 'react'
import { ChevronDown, ReceiptText } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { EvidenceSummary } from '@/lib/types/research'
import { EvidenceSummaryPanel } from './EvidenceSummaryPanel'

export interface EvidenceCostCardProps {
  evidenceSummary: EvidenceSummary | null | undefined
}

export function EvidenceCostCard({ evidenceSummary }: EvidenceCostCardProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)

  const evidenceItems = Array.isArray(evidenceSummary?.evidence_items)
    ? evidenceSummary.evidence_items
    : []

  return (
    <div className="card space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h3 className="inline-flex items-center gap-2 text-sm font-semibold font-heading text-foreground">
          <ReceiptText className="h-4 w-4 text-cta" />
          {t('report.transparency.evidence.title')}
        </h3>
        {evidenceItems.length > 3 && (
          <button
            onClick={() => setExpanded(prev => !prev)}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-none px-1 py-0.5 text-xs font-bold uppercase tracking-wider text-muted-foreground transition-colors hover:text-cta focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform duration-300 ease-out ${expanded ? 'rotate-180' : ''}`}
            />
            {expanded ? t('report.hero.showLess') : t('report.hero.readMore')}
          </button>
        )}
      </div>

      <EvidenceSummaryPanel evidenceSummary={evidenceSummary} expanded={expanded} />
    </div>
  )
}
