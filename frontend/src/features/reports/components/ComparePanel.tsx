import { useEffect, useId, useRef, useMemo } from 'react'
import { X, Check, Minus, Globe } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/Badge'
import { RelevanceRing } from './RelevanceRing'
import { getCompetitorId } from '../competitor'
import { PlatformIcon, platformColors } from './PlatformIcons'
import type { Competitor } from '@/lib/types/research'

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

  const allFeatures = useMemo(() => Array.from(
    new Set(competitors.flatMap(c => c.features))
  ).sort(), [competitors])

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
      document.removeEventListener('keydown', onKeyDown)
      previousFocusedRef.current?.focus()
    }
  }, [onClose])

  if (competitors.length < 2) return null

  return (
    <div
      id="compare-panel"
      className="relative z-10 w-full animate-fade-in"
      role="region"
      aria-labelledby={headingId}
      ref={dialogRef}
    >
      <div
        ref={panelRef}
        className="w-full bg-card border-2 border-border shadow-[4px_4px_0px_0px_var(--border)] overflow-hidden flex flex-col my-8"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-2 border-border shrink-0 bg-muted/45">
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

        {/* Desktop Table View / Mobile Stacked View */}
        <div className="overflow-y-auto overflow-x-hidden flex-1 p-0 sm:p-0">

          {/* --- MOBILE VIEW (Stacked Cards) --- */}
          <div className="block sm:hidden p-4 space-y-6">
            {competitors.map(competitor => {
              const competitorId = getCompetitorId(competitor)
              return (
                <div key={competitorId} className="rounded-none border border-2 border-border bg-card p-4 shadow-[4px_4px_0px_0px_var(--border)] relative">
                  <button
                    type="button"
                    onClick={() => onRemove(competitorId)}
                    className="absolute top-3 right-3 p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-none text-muted-foreground hover:text-danger bg-muted/50 transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary"
                    aria-label={`Remove ${competitor.name}`}
                  >
                    <X className="w-4 h-4" />
                  </button>

                  <h4 className="text-lg font-bold text-foreground pr-12 mb-3">{competitor.name}</h4>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">{t('report.compare.relevance')}</span>
                      <RelevanceRing score={competitor.relevance_score} size={36} />
                    </div>
                    <div>
                      <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-1">{t('report.compare.pricing')}</span>
                      <span className="text-sm font-medium text-foreground">{competitor.pricing ?? '-'}</span>
                    </div>
                  </div>

                <div className="mb-6">
                  <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-2">{t('report.compare.description')}</span>
                  <p className="text-sm text-foreground leading-relaxed">{competitor.one_liner}</p>
                </div>

                  {allFeatures.length > 0 && (
                    <div className="mb-4">
                    <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-2">{t('report.compare.features')}</span>
                    <div className="flex flex-wrap gap-2">
                        {allFeatures.map(feature => {
                          const hasFeature = competitor.features.includes(feature)
                          if (!hasFeature) return null
                          return (
                            <Badge key={feature} variant="accent" className="px-2.5 py-1 text-xs font-medium border-cta/20 leading-tight">
                              <Check className="w-3 h-3 shrink-0" />
                              {feature}
                            </Badge>
                          )
                        })}
                    </div>
                    </div>
                  )}

                  {(competitor.strengths.length > 0 || competitor.weaknesses.length > 0) && (
                    <div className="space-y-3 pt-3 border-t border-2 border-border">
                      {competitor.strengths.length > 0 && (
                        <div>
                          <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">{t('report.compare.strengths')}</span>
                          <ul className="space-y-1.5">
                            {competitor.strengths.map((s, i) => (
                              <li key={i} className="text-sm text-foreground flex items-start gap-1.5 leading-snug">
                                <span className="text-success mt-0.5 shrink-0">•</span> <span>{s}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {competitor.weaknesses.length > 0 && (
                        <div>
                          <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">{t('report.compare.weaknesses')}</span>
                          <ul className="space-y-1.5">
                            {competitor.weaknesses.map((w, i) => (
                              <li key={i} className="text-sm text-foreground flex items-start gap-1.5 leading-snug">
                                <span className="text-danger mt-0.5 shrink-0">•</span> <span>{w}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* --- DESKTOP VIEW (Table) --- */}
          <div className="hidden sm:block w-full overflow-x-auto">
            <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-2 border-border">
                <th className="sticky left-0 bg-popover z-10 text-left px-5 py-4 text-xs font-medium text-muted-foreground w-36 min-w-36" />
                {competitors.map(competitor => {
                  const competitorId = getCompetitorId(competitor)
                  return (
                    <th key={competitorId} className="px-4 py-3 text-left min-w-44 border-l border-2 border-border">
                      <div className="flex items-center justify-between gap-2 min-w-0">
                        <span className="text-sm font-semibold text-foreground truncate min-w-0" title={competitor.name}>
                          {competitor.name}
                        </span>
                        <button
                          type="button"
                          onClick={() => onRemove(competitorId)}
                          className="p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-none text-muted-foreground hover:text-danger hover:bg-muted/50 transition-colors cursor-pointer shrink-0 focus-visible:ring-2 focus-visible:ring-primary"
                          aria-label={`Remove ${competitor.name}`}
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {/* Relevance */}
              <tr className="border-b border-2 border-border">
                <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium">{t('report.compare.relevance')}</td>
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-relevance`} className="px-4 py-3 border-l border-2 border-border">
                    <RelevanceRing score={competitor.relevance_score} size={32} />
                  </td>
                ))}
              </tr>

              {/* One-liner */}
              <tr className="border-b border-2 border-border/30">
                <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium">{t('report.compare.description')}</td>
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-description`} className="px-4 py-3 text-xs text-foreground leading-relaxed border-l border-2 border-border break-words min-w-[200px] whitespace-normal">{competitor.one_liner}</td>
                ))}
              </tr>

              {/* Pricing */}
              <tr className="border-b border-2 border-border/30">
                <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium">{t('report.compare.pricing')}</td>
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-pricing`} className="px-4 py-3 text-xs text-foreground font-medium border-l border-2 border-border">{competitor.pricing ?? '-'}</td>
                ))}
              </tr>

              {/* Features */}
              {allFeatures.length > 0 && (
                <tr className="border-b border-2 border-border">
                  <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-foreground uppercase tracking-wider bg-muted/65">
                    {t('report.compare.features')}
                  </td>
                </tr>
              )}
              {allFeatures.map(feature => (
                <tr key={feature} className="border-b border-2 border-border/30">
                  <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground break-words max-w-[150px] whitespace-normal">{feature}</td>
                  {competitors.map(competitor => (
                    <td key={`${getCompetitorId(competitor)}-${feature}`} className="px-4 py-2 text-center border-l border-2 border-border">
                      {competitor.features.includes(feature) ? (
                        <Check className="w-4 h-4 text-cta inline-block" />
                      ) : (
                        <Minus className="w-4 h-4 text-muted-foreground/40 inline-block" />
                      )}
                    </td>
                  ))}
                </tr>
              ))}

              {/* Strengths */}
              <tr className="border-b border-2 border-border">
                <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-foreground uppercase tracking-wider bg-muted/65">
                  {t('report.compare.strengths')}
                </td>
              </tr>
              <tr className="border-b border-2 border-border/30">
                <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium" />
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-strengths`} className="px-4 py-4 align-top border-l border-2 border-border min-w-[200px] break-words whitespace-normal">
                    <ul className="space-y-2">
                      {competitor.strengths.map((s, i) => (
                        <li key={i} className="text-xs text-foreground flex items-start gap-1.5 leading-snug"><span className="text-success shrink-0">&bull;</span> <span>{s}</span></li>
                      ))}
                    </ul>
                  </td>
                ))}
              </tr>

              {/* Weaknesses */}
              <tr className="border-b border-2 border-border">
                <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-foreground uppercase tracking-wider bg-muted/65">
                  {t('report.compare.weaknesses')}
                </td>
              </tr>
              <tr className="border-b border-2 border-border/30">
                <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium" />
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-weaknesses`} className="px-4 py-4 align-top border-l border-2 border-border min-w-[200px] break-words whitespace-normal">
                    <ul className="space-y-2">
                      {competitor.weaknesses.map((w, i) => (
                        <li key={i} className="text-xs text-foreground flex items-start gap-1.5 leading-snug"><span className="text-danger shrink-0">&bull;</span> <span>{w}</span></li>
                      ))}
                    </ul>
                  </td>
                ))}
              </tr>

              {/* Sources */}
              <tr>
                <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium">{t('report.compare.sources')}</td>
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-sources`} className="px-4 py-3 border-l border-2 border-border">
                    <div className="flex gap-2 flex-wrap shrink-0 max-w-[150px]">
                      {competitor.source_platforms.map(p => {
                        const Icon = PlatformIcon[p] || Globe
                        return (
                          <Badge key={p} variant="default" className={`text-[10px] pl-1 pr-1.5 py-0.5 whitespace-nowrap ${platformColors[p] || ''}`}>
                            <Icon className="w-3 h-3" />
                            {p}
                          </Badge>
                        )
                      })}
                    </div>
                  </td>
                ))}
              </tr>
            </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  )
}

/* Floating compare bar shown when >= 2 competitors are selected */
interface CompareFloatingBarProps {
  count: number
  onCompare: () => void
  onClear: () => void
}

export function CompareFloatingBar({ count, onCompare, onClear }: CompareFloatingBarProps) {
  const { t } = useTranslation()
  if (count < 2) return null

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-4 px-6 py-3.5 rounded-none bg-popover/95  border border-2 border-border shadow-[4px_4px_0px_0px_var(--border)] animate-fade-in no-print">
      <span className="text-sm text-foreground">
        <span className="font-semibold text-cta">{count}</span> {t('report.compare.selected')}
      </span>
      <button
        type="button"
        onClick={() => {
          onCompare()
          setTimeout(() => {
            document.getElementById('compare-panel')?.scrollIntoView({ behavior: 'smooth' })
          }, 50)
        }}
        className="px-5 py-2 text-sm font-semibold rounded-none bg-cta text-primary-foreground cursor-pointer transition-all duration-300 hover:bg-cta-hover hover:shadow-[4px_4px_0px_0px_var(--border)] hover:-translate-y-px focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        {t('report.compare.compareBtn')}
      </button>
      <button
        type="button"
        onClick={onClear}
        className="text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 rounded-none px-1"
      >
        {t('report.compare.clear')}
      </button>
    </div>
  )
}
