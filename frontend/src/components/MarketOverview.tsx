import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'

interface MarketOverviewProps {
  summary: string
}

export function MarketOverview({ summary }: MarketOverviewProps) {
  const [expanded, setExpanded] = useState(false)
  const isLong = summary.length > 300

  if (!summary) return null

  return (
    <div>
      <h2 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text mb-3">
        Market Overview
      </h2>
      <div className="relative">
        <p className={`text-sm text-text-muted leading-relaxed whitespace-pre-line ${!expanded && isLong ? 'line-clamp-4' : ''}`}>
          {summary}
        </p>
        {!expanded && isLong && (
          <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-bg to-transparent pointer-events-none" />
        )}
      </div>
      {isLong && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="mt-2 inline-flex items-center gap-1 text-xs text-text-muted hover:text-cta transition-colors cursor-pointer"
        >
          {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          {expanded ? 'Show less' : 'Read more'}
        </button>
      )}
    </div>
  )
}
