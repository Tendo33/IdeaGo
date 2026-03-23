import { useEffect, useId, useMemo, useRef } from 'react'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { Competitor } from '@/lib/types/research'
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
  const dialogRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const previousFocusedRef = useRef<HTMLElement | null>(null)

  const allFeatures = useMemo(
    () => Array.from(new Set(competitors.flatMap(competitor => competitor.features))).sort(),
    [competitors],
  )

  const getFocusableElements = () => {
    const panel = panelRef.current
    if (!panel) return []
    return Array.from(
      panel.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    )
  }

  useEffect(() => {
    previousFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const focusable = getFocusableElements()
    const firstFocusable = focusable[0]
    if (firstFocusable) {
      firstFocusable.focus()
    } else {
      dialogRef.current?.focus()
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
      if (event.key === 'Tab') {
        const focusableElements = getFocusableElements()
        if (focusableElements.length === 0) return
        const first = focusableElements[0]
        const last = focusableElements[focusableElements.length - 1]
        const activeElement = document.activeElement
        if (event.shiftKey && activeElement === first) {
          event.preventDefault()
          last.focus()
        } else if (!event.shiftKey && activeElement === last) {
          event.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeyDown)
      previousFocusedRef.current?.focus()
    }
  }, [onClose])

  if (competitors.length < 2) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:p-6"
      role="presentation"
    >
      <div
        aria-hidden="true"
        className="absolute inset-0 bg-background/80 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
      id="compare-panel"
      className="relative z-10 flex w-full max-w-6xl animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby={headingId}
      ref={dialogRef}
      tabIndex={-1}
    >
      <div
        ref={panelRef}
        className="flex max-h-[min(88vh,960px)] w-full flex-col overflow-hidden border-2 border-border bg-card shadow"
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
      </div>
    </div>
  )
}

export { CompareFloatingBar } from './CompareFloatingBar'
export type { CompareFloatingBarProps } from './CompareFloatingBar'
export type { ComparePanelProps }
