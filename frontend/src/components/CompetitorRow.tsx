import { ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getCompetitorDomId } from '../competitor'
import { RelevanceRing } from './RelevanceRing'
import type { Competitor } from '../types/research'

const platformColors: Record<string, string> = {
  github: 'bg-chart-2/15 text-chart-2',
  tavily: 'bg-chart-3/15 text-chart-3',
  hackernews: 'bg-chart-5/15 text-chart-5',
  appstore: 'bg-chart-1/15 text-chart-1',
}

interface CompetitorRowProps {
  competitor: Competitor
  rank: number
  domId?: string
  compareSelected?: boolean
  onToggleCompare?: () => void
}

export function CompetitorRow({ competitor, rank, domId, compareSelected, onToggleCompare }: CompetitorRowProps) {
  const { t } = useTranslation()
  const primaryLink = competitor.links[0]
  const elementId = domId ?? getCompetitorDomId(competitor)

  return (
    <div
      id={elementId}
      className="flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-bg-card/85 backdrop-blur-md transition-all duration-300 hover:border-cta/30 hover:bg-muted/55 hover:-translate-y-px group"
    >
      <span className="text-xs font-mono text-text-dim w-6 text-right shrink-0">#{rank}</span>
      <RelevanceRing score={competitor.relevance_score} size={28} />

      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text truncate group-hover:text-cta transition-colors">
          {competitor.name}
        </p>
        <p className="text-xs text-text-dim truncate">{competitor.one_liner}</p>
      </div>

      <div className="flex flex-wrap gap-1.5 shrink-0 max-w-30 justify-end">
        {competitor.source_platforms.map(p => (
          <span key={p} className={`text-[10px] px-1.5 py-0.5 rounded-full whitespace-nowrap ${platformColors[p] || 'bg-secondary/50 text-text-dim'}`}>
            {p}
          </span>
        ))}
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {onToggleCompare && (
          <button
            onClick={e => { e.stopPropagation(); onToggleCompare() }}
            className={`text-xs px-2 py-1 rounded-md border cursor-pointer transition-colors duration-150 ${
              compareSelected
                ? 'border-cta/50 bg-cta/10 text-cta'
                : 'border-border text-text-dim hover:border-cta/30'
            }`}
            aria-label={compareSelected ? t('report.competitors.compareSelected') : t('report.competitors.compareUnselected')}
          >
            {compareSelected ? t('report.competitors.compareSelected') : t('report.competitors.compareUnselected')}
          </button>
        )}
        {primaryLink && (
          <a
            href={primaryLink}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded-md text-text-dim hover:text-cta transition-colors"
            aria-label={`Open ${competitor.name}`}
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    </div>
  )
}
