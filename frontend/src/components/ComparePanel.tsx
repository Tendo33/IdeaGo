import { useEffect, useRef } from 'react'
import { X, Check, Minus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { RelevanceRing } from './RelevanceRing'
import type { Competitor } from '../types/research'

interface ComparePanelProps {
  competitors: Competitor[]
  onRemove: (name: string) => void
  onClose: () => void
}

export function ComparePanel({ competitors, onRemove, onClose }: ComparePanelProps) {
  const { t } = useTranslation()
  const dialogRef = useRef<HTMLDivElement>(null)
  if (competitors.length < 2) return null

  const allFeatures = Array.from(
    new Set(competitors.flatMap(c => c.features))
  ).sort()

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  useEffect(() => {
    dialogRef.current?.focus()
  }, [])

  if (competitors.length < 2) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Compare competitors"
      tabIndex={-1}
      ref={dialogRef}
    >
      <div className="w-full max-w-5xl max-h-[85vh] bg-bg-card border border-border rounded-t-2xl sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <h3 className="text-lg font-semibold font-heading text-text">
            {t('report.compare.title', { count: competitors.length })}
          </h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-text-dim hover:text-text hover:bg-secondary transition-colors cursor-pointer"
            aria-label="Close comparison panel"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Table */}
        <div className="overflow-auto flex-1">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-border">
                <th className="sticky left-0 bg-bg-card z-10 text-left px-4 py-3 text-xs font-medium text-text-dim w-36 min-w-36" />
                {competitors.map(c => (
                  <th key={c.name} className="px-4 py-3 text-left min-w-44">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-text truncate">{c.name}</span>
                      <button
                        onClick={() => onRemove(c.name)}
                        className="p-1 rounded text-text-dim hover:text-danger transition-colors cursor-pointer shrink-0"
                        aria-label={`Remove ${c.name}`}
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Relevance */}
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-bg-card z-10 px-4 py-2.5 text-xs text-text-dim font-medium">{t('report.compare.relevance')}</td>
                {competitors.map(c => (
                  <td key={c.name} className="px-4 py-2.5">
                    <RelevanceRing score={c.relevance_score} size={32} />
                  </td>
                ))}
              </tr>

              {/* One-liner */}
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-bg-card z-10 px-4 py-2.5 text-xs text-text-dim font-medium">{t('report.compare.description')}</td>
                {competitors.map(c => (
                  <td key={c.name} className="px-4 py-2.5 text-xs text-text-muted">{c.one_liner}</td>
                ))}
              </tr>

              {/* Pricing */}
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-bg-card z-10 px-4 py-2.5 text-xs text-text-dim font-medium">{t('report.compare.pricing')}</td>
                {competitors.map(c => (
                  <td key={c.name} className="px-4 py-2.5 text-xs text-text-muted">{c.pricing ?? '—'}</td>
                ))}
              </tr>

              {/* Features */}
              {allFeatures.length > 0 && (
                <tr className="border-b border-border">
                  <td colSpan={competitors.length + 1} className="px-4 py-2 text-xs font-semibold text-text-dim uppercase tracking-wider bg-secondary/30">
                    {t('report.compare.features')}
                  </td>
                </tr>
              )}
              {allFeatures.map(feature => (
                <tr key={feature} className="border-b border-border/30">
                  <td className="sticky left-0 bg-bg-card z-10 px-4 py-2 text-xs text-text-muted">{feature}</td>
                  {competitors.map(c => (
                    <td key={c.name} className="px-4 py-2 text-center">
                      {c.features.includes(feature) ? (
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
                <td colSpan={competitors.length + 1} className="px-4 py-2 text-xs font-semibold text-text-dim uppercase tracking-wider bg-secondary/30">
                  {t('report.compare.strengths')}
                </td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-bg-card z-10 px-4 py-2.5 text-xs text-text-dim font-medium" />
                {competitors.map(c => (
                  <td key={c.name} className="px-4 py-2.5 align-top">
                    <ul className="space-y-0.5">
                      {c.strengths.map((s, i) => (
                        <li key={i} className="text-xs text-cta">&bull; {s}</li>
                      ))}
                    </ul>
                  </td>
                ))}
              </tr>

              {/* Weaknesses */}
              <tr className="border-b border-border">
                <td colSpan={competitors.length + 1} className="px-4 py-2 text-xs font-semibold text-text-dim uppercase tracking-wider bg-secondary/30">
                  {t('report.compare.weaknesses')}
                </td>
              </tr>
              <tr className="border-b border-border/50">
                <td className="sticky left-0 bg-bg-card z-10 px-4 py-2.5 text-xs text-text-dim font-medium" />
                {competitors.map(c => (
                  <td key={c.name} className="px-4 py-2.5 align-top">
                    <ul className="space-y-0.5">
                      {c.weaknesses.map((w, i) => (
                        <li key={i} className="text-xs text-danger">&bull; {w}</li>
                      ))}
                    </ul>
                  </td>
                ))}
              </tr>

              {/* Sources */}
              <tr>
                <td className="sticky left-0 bg-bg-card z-10 px-4 py-2.5 text-xs text-text-dim font-medium">{t('report.compare.sources')}</td>
                {competitors.map(c => (
                  <td key={c.name} className="px-4 py-2.5">
                    <div className="flex gap-1.5 flex-wrap">
                      {c.source_platforms.map(p => (
                        <span key={p} className="text-[10px] px-1.5 py-0.5 rounded-full bg-secondary/50 text-text-dim">{p}</span>
                      ))}
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
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 px-5 py-3 rounded-xl bg-bg-card border border-cta/30 shadow-xl shadow-black/30 animate-fade-in no-print">
      <span className="text-sm text-text">
        <span className="font-semibold text-cta">{count}</span> {t('report.compare.selected')}
      </span>
      <button
        onClick={onCompare}
        className="px-4 py-1.5 text-sm font-medium rounded-lg bg-cta text-white cursor-pointer transition-colors hover:bg-cta-hover"
      >
        {t('report.compare.compareBtn')}
      </button>
      <button
        onClick={onClear}
        className="text-xs text-text-dim hover:text-text cursor-pointer transition-colors"
      >
        {t('report.compare.clear')}
      </button>
    </div>
  )
}
