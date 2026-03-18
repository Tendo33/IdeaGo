import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface MarketOverviewProps {
  summary: string
}

export function MarketOverview({ summary }: MarketOverviewProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const isLong = summary.length > 300

  if (!summary) return null

  return (
    <div>
      <h2 className="text-lg font-semibold font-heading text-foreground mb-3">
        {t('report.market.title')}
      </h2>
      <div className="relative">
        <p className={`text-sm text-muted-foreground leading-relaxed whitespace-pre-line break-words ${!expanded && isLong ? 'line-clamp-4' : ''}`}>
          {summary}
        </p>
        {!expanded && isLong && (
          <div className="absolute bottom-0 left-0 right-0 h-8 bg-linear-to-t from-bg to-transparent pointer-events-none" />
        )}
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="mt-2 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-cta transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none rounded-none px-1"
        >
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          {expanded ? t('report.hero.showLess') : t('report.hero.readMore')}
        </button>
      )}
    </div>
  )
}
