import { useEffect, useId, useRef } from 'react'
import { X, Check, Minus, Github, Globe, Terminal, Smartphone, Flame } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { RelevanceRing } from './RelevanceRing'
import { getCompetitorId } from '../competitor'
import type { Competitor } from '../types/research'

const platformColors: Record<string, string> = {
  github: 'bg-chart-2/15 text-chart-2',
  tavily: 'bg-chart-3/15 text-chart-3',
  producthunt: 'bg-chart-4/15 text-chart-4',
  hackernews: 'bg-chart-5/15 text-chart-5',
  appstore: 'bg-chart-1/15 text-chart-1',
}

const PlatformIcon: Record<string, React.ElementType> = {
  github: Github,
  tavily: Globe,
  producthunt: Flame,
  hackernews: Terminal,
  appstore: Smartphone,
}

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

  const allFeatures = Array.from(
    new Set(competitors.flatMap(c => c.features))
  ).sort()

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
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-foreground/45 backdrop-blur-md"
      role="dialog"
      aria-modal="true"
      aria-labelledby={headingId}
      tabIndex={-1}
      ref={dialogRef}
      onMouseDown={event => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        ref={panelRef}
        className="w-full max-w-5xl max-h-[85vh] bg-popover/95 backdrop-blur-2xl border border-border/80 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden flex flex-col"
        onMouseDown={event => event.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-border/80 shrink-0 bg-muted/45">
          <h3 id={headingId} className="text-lg font-semibold font-heading text-text">
            {t('report.compare.title', { count: competitors.length })}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-dim hover:text-text hover:bg-secondary transition-colors cursor-pointer"
            aria-label={t('report.compare.closePanel')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Table */}
        <div className="overflow-auto flex-1">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="sticky left-0 bg-popover/95 z-10 text-left px-5 py-4 text-xs font-medium text-text-dim w-36 min-w-36 backdrop-blur-xl" />
                {competitors.map(competitor => {
                  const competitorId = getCompetitorId(competitor)
                  return (
                    <th key={competitorId} className="px-4 py-3 text-left min-w-44">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold text-text truncate">{competitor.name}</span>
                        <button
                          type="button"
                          onClick={() => onRemove(competitorId)}
                          className="p-1 rounded text-text-dim hover:text-danger transition-colors cursor-pointer shrink-0"
                          aria-label={`Remove ${competitor.name}`}
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {/* Relevance */}
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-popover/95 z-10 px-5 py-3 text-xs text-text-muted font-medium backdrop-blur-xl">{t('report.compare.relevance')}</td>
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-relevance`} className="px-4 py-2.5">
                    <RelevanceRing score={competitor.relevance_score} size={32} />
                  </td>
                ))}
              </tr>

              {/* One-liner */}
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-popover/95 z-10 px-5 py-3 text-xs text-text-muted font-medium backdrop-blur-xl">{t('report.compare.description')}</td>
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-description`} className="px-4 py-2.5 text-xs text-text-muted">{competitor.one_liner}</td>
                ))}
              </tr>

              {/* Pricing */}
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-popover/95 z-10 px-5 py-3 text-xs text-text-muted font-medium backdrop-blur-xl">{t('report.compare.pricing')}</td>
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-pricing`} className="px-4 py-2.5 text-xs text-text-muted">{competitor.pricing ?? '-'}</td>
                ))}
              </tr>

              {/* Features */}
              {allFeatures.length > 0 && (
                <tr className="border-b border-border">
                  <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-text uppercase tracking-wider bg-muted/65">
                    {t('report.compare.features')}
                  </td>
                </tr>
              )}
              {allFeatures.map(feature => (
                <tr key={feature} className="border-b border-border/30">
                  <td className="sticky left-0 bg-popover/95 z-10 px-5 py-3 text-xs text-text-muted backdrop-blur-xl">{feature}</td>
                  {competitors.map(competitor => (
                    <td key={`${getCompetitorId(competitor)}-${feature}`} className="px-4 py-2 text-center">
                      {competitor.features.includes(feature) ? (
                        <Check className="w-4 h-4 text-cta inline-block" />
                      ) : (
                        <Minus className="w-4 h-4 text-text-dim/40 inline-block" />
                      )}
                    </td>
                  ))}
                </tr>
              ))}

              {/* Strengths */}
              <tr className="border-b border-border">
                <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-text uppercase tracking-wider bg-muted/65">
                  {t('report.compare.strengths')}
                </td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-popover/95 z-10 px-5 py-3 text-xs text-text-dim font-medium backdrop-blur-xl" />
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-strengths`} className="px-4 py-2.5 align-top">
                    <ul className="space-y-0.5">
                      {competitor.strengths.map((s, i) => (
                        <li key={i} className="text-xs text-cta">&bull; {s}</li>
                      ))}
                    </ul>
                  </td>
                ))}
              </tr>

              {/* Weaknesses */}
              <tr className="border-b border-border">
                <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-text uppercase tracking-wider bg-muted/65">
                  {t('report.compare.weaknesses')}
                </td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-popover/95 z-10 px-5 py-3 text-xs text-text-dim font-medium backdrop-blur-xl" />
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-weaknesses`} className="px-4 py-2.5 align-top">
                    <ul className="space-y-0.5">
                      {competitor.weaknesses.map((w, i) => (
                        <li key={i} className="text-xs text-danger">&bull; {w}</li>
                      ))}
                    </ul>
                  </td>
                ))}
              </tr>

              {/* Sources */}
              <tr>
                <td className="sticky left-0 bg-popover/95 z-10 px-5 py-3 text-xs text-text-muted font-medium backdrop-blur-xl">{t('report.compare.sources')}</td>
                {competitors.map(competitor => (
                  <td key={`${getCompetitorId(competitor)}-sources`} className="px-4 py-2.5">
                    <div className="flex gap-1.5 flex-wrap">
                      {competitor.source_platforms.map(p => {
                        const Icon = PlatformIcon[p] || Globe
                        return (
                          <span key={p} className={`inline-flex items-center gap-1 text-[10px] pl-1 pr-1.5 py-0.5 rounded-full whitespace-nowrap ${platformColors[p] || 'bg-secondary/50 text-text-dim'}`}>
                            <Icon className="w-3 h-3" />
                            {p}
                          </span>
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
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-4 px-6 py-3.5 rounded-2xl bg-popover/95 backdrop-blur-xl border border-border shadow-xl animate-fade-in no-print">
      <span className="text-sm text-text">
        <span className="font-semibold text-cta">{count}</span> {t('report.compare.selected')}
      </span>
      <button
        type="button"
        onClick={onCompare}
        className="px-5 py-2 text-sm font-semibold rounded-xl bg-cta text-primary-foreground cursor-pointer transition-all duration-300 hover:bg-cta-hover hover:shadow-lg hover:-translate-y-px"
      >
        {t('report.compare.compareBtn')}
      </button>
      <button
        type="button"
        onClick={onClear}
        className="text-xs text-text-dim hover:text-text cursor-pointer transition-colors"
      >
        {t('report.compare.clear')}
      </button>
    </div>
  )
}
