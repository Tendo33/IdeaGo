import { useState } from 'react'
import { Activity, ChevronDown } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export interface MarketOverviewProps {
  summary: string
}

function splitSummary(summary: string): string[] {
  return summary
    .split(/\n+/)
    .map(part => part.trim())
    .filter(Boolean)
}

export function MarketOverview({ summary }: MarketOverviewProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const paragraphs = splitSummary(summary)
  const primary = paragraphs[0] || ''
  const secondary = paragraphs.slice(1)
  const hiddenParagraphs = expanded ? secondary : secondary.slice(0, 2)
  const isLong = summary.length > 320 || secondary.length > 2

  if (!summary) return null

  return (
    <div className="card overflow-hidden">
      <div className="space-y-4">
        <div className="inline-flex items-center gap-2 border border-border bg-background px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
          <Activity className="h-3.5 w-3.5 text-cta" />
          {t('report.market.whyNow')}
        </div>
        <div className="space-y-3">
          <h2 className="text-xl font-bold font-heading text-foreground">
            {t('report.market.contextAndTiming')}
          </h2>
          <p className="text-base leading-relaxed text-foreground whitespace-pre-line break-words">
            {primary}
          </p>
        </div>

        {hiddenParagraphs.length > 0 ? (
          <div className="space-y-3">
            {hiddenParagraphs.map(paragraph => (
              <p
                key={paragraph}
                className="text-sm leading-relaxed text-muted-foreground whitespace-pre-line break-words"
              >
                {paragraph}
              </p>
            ))}
          </div>
        ) : null}

        {isLong ? (
          <button
            onClick={() => setExpanded(current => !current)}
            className="inline-flex items-center gap-1.5 px-1 py-0.5 text-xs font-bold uppercase tracking-wider text-muted-foreground transition-colors duration-200 hover:text-cta focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          >
            <ChevronDown
              className={`h-3.5 w-3.5 transition-transform duration-300 ease-out ${expanded ? 'rotate-180' : ''}`}
            />
            {expanded ? t('report.market.showLessContext') : t('report.market.readFullContext')}
          </button>
        ) : null}
      </div>
    </div>
  )
}
