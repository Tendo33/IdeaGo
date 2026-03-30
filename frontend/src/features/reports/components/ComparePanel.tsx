import { useId, useMemo } from 'react'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Competitor } from '@/lib/types/research'
import { Dialog } from '@/components/ui/Dialog'
import { ComparePanelDesktopTable } from './ComparePanelDesktopTable'
import { ComparePanelMobileView } from './ComparePanelMobileView'

interface ComparePanelProps {
  competitors: Competitor[]
  onRemove: (competitorId: string) => void
  onClose: () => void
}

export function ComparePanel({ competitors, onRemove, onClose }: ComparePanelProps) {
  const { t } = useTranslation()
  const headingId = useId()

  const allFeatures = useMemo(
    () => Array.from(new Set(competitors.flatMap(competitor => competitor.features))).sort(),
    [competitors],
  )

  if (competitors.length < 2) return null

  return (
    <Dialog
      open={competitors.length >= 2}
      onClose={onClose}
      labelledBy={headingId}
      panelClassName="relative z-10 flex w-full max-w-6xl animate-fade-in"
    >
      <div
        className="flex max-h-[min(88vh,960px)] w-full flex-col border-2 border-border bg-card shadow"
      >
        <div className="flex items-center justify-between px-6 py-5 border-b-2 border-border shrink-0 bg-muted/45">
          <h3 id={headingId} className="text-lg font-semibold font-heading text-foreground">
            {t('report.compare.title', { count: competitors.length })}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-none text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary"
            aria-label={t('report.compare.closePanel')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="overflow-y-auto overflow-x-hidden flex-1 p-0 sm:p-0">
          <ComparePanelMobileView competitors={competitors} allFeatures={allFeatures} onRemove={onRemove} />
          <ComparePanelDesktopTable competitors={competitors} allFeatures={allFeatures} onRemove={onRemove} />
        </div>
      </div>
    </Dialog>
  )
}

export { CompareFloatingBar } from './CompareFloatingBar'
export type { CompareFloatingBarProps } from './CompareFloatingBar'
export type { ComparePanelProps }
