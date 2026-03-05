import { useState } from 'react'
import { ExternalLink, ThumbsUp, ThumbsDown, Tag, DollarSign, ChevronDown, ChevronUp, Award } from 'lucide-react'
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

interface CompetitorCardProps {
  competitor: Competitor
  rank: number
  domId?: string
  variant?: 'featured' | 'standard'
  compareSelected?: boolean
  onToggleCompare?: () => void
}

function LinkWithHost({ link, name }: { link: string; name: string }) {
  let hostname = 'link'
  try {
    const u = new URL(link)
    hostname = u.hostname.replace(/^www\./, '')
  } catch { /* use defaults */ }

  return (
    <a
      href={link}
      target="_blank"
      rel="noopener noreferrer"
      onClick={e => e.stopPropagation()}
      className="inline-flex items-center gap-1.5 text-xs text-cta hover:text-cta-hover transition-colors duration-200 cursor-pointer"
      aria-label={`Open ${name} on ${hostname}`}
    >
      <ExternalLink className="w-3 h-3" />
      {hostname}
    </a>
  )
}

export function CompetitorCard({
  competitor,
  rank,
  domId,
  variant = 'standard',
  compareSelected,
  onToggleCompare,
}: CompetitorCardProps) {
  const { t } = useTranslation()
  const isFeatured = variant === 'featured'
  const [isExpanded, setIsExpanded] = useState(isFeatured)
  const elementId = domId ?? getCompetitorDomId(competitor)

  const featuresLimit = isExpanded ? competitor.features.length : 4
  const prosLimit = isExpanded ? competitor.strengths.length : 3
  const consLimit = isExpanded ? competitor.weaknesses.length : 3
  const hasMore =
    competitor.features.length > 4 ||
    competitor.strengths.length > 3 ||
    competitor.weaknesses.length > 3

  return (
    <div
      id={elementId}
      className={`card select-none ${
        isFeatured
          ? 'border-l-4! border-l-cta! border-t-border/80! border-r-border/80! border-b-border/80! col-span-full'
          : 'card-clickable p-5!'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-xs font-mono text-text-dim">#{rank}</span>
            {isFeatured && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-cta/15 text-cta">
                <Award className="w-3 h-3" />
                {t('report.competitors.top')}
              </span>
            )}
            <h3 className={`font-semibold font-heading text-text truncate ${isFeatured ? 'text-xl' : 'text-lg'}`}>
              {competitor.name}
            </h3>
          </div>
          <p className="text-sm text-text-muted leading-relaxed">{competitor.one_liner}</p>
        </div>
        <RelevanceRing score={competitor.relevance_score} size={isFeatured ? 44 : 36} />
      </div>

      {/* Feature Tags */}
      {competitor.features.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {competitor.features.slice(0, featuresLimit).map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-secondary/50 text-text-muted">
              <Tag className="w-3 h-3" />{f}
            </span>
          ))}
          {!isExpanded && competitor.features.length > 4 && (
            <span className="text-xs text-text-dim self-center">+{competitor.features.length - 4} {t('report.competitors.more')}</span>
          )}
        </div>
      )}

      {/* Pricing */}
      {competitor.pricing && (
        <div className="flex items-center gap-1.5 text-xs text-text-muted mb-3">
          <DollarSign className="w-3.5 h-3.5" />
          <span>{competitor.pricing}</span>
        </div>
      )}

      {/* Strengths / Weaknesses */}
      {(isExpanded || isFeatured) && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          {competitor.strengths.length > 0 && (
            <div>
              <div className="flex items-center gap-1 text-xs text-cta mb-1.5">
                <ThumbsUp className="w-3 h-3" /> {t('report.competitors.strengths')}
              </div>
              <ul className="space-y-0.5">
                {competitor.strengths.slice(0, prosLimit).map((s, i) => (
                  <li key={i} className="text-xs text-text-muted">&bull; {s}</li>
                ))}
              </ul>
            </div>
          )}
          {competitor.weaknesses.length > 0 && (
            <div>
              <div className="flex items-center gap-1 text-xs text-danger mb-1.5">
                <ThumbsDown className="w-3 h-3" /> {t('report.competitors.weaknesses')}
              </div>
              <ul className="space-y-0.5">
                {competitor.weaknesses.slice(0, consLimit).map((w, i) => (
                  <li key={i} className="text-xs text-text-muted">&bull; {w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-border gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex gap-1.5 shrink-0">
            {competitor.source_platforms.map(p => (
              <span key={p} className={`text-xs px-2 py-0.5 rounded-full ${platformColors[p] || 'bg-secondary/50 text-text-dim'}`}>
                {p}
              </span>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {competitor.links.slice(0, isExpanded ? competitor.links.length : 2).map((link, i) => (
              <LinkWithHost key={i} link={link} name={competitor.name} />
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {onToggleCompare && (
            <button
              onClick={e => { e.stopPropagation(); onToggleCompare() }}
              className={`text-xs px-2.5 py-1 rounded-md border cursor-pointer transition-all duration-300 ${
                compareSelected
                  ? 'border-cta/50 bg-cta/10 text-cta'
                  : 'border-border/80 text-text-dim hover:border-cta/30 hover:text-text-muted hover:bg-muted/55'
              }`}
            >
              {compareSelected ? t('report.competitors.compareSelected') : t('report.competitors.compareUnselected')}
            </button>
          )}
          {!isFeatured && hasMore && (
            <button
              onClick={() => setIsExpanded(prev => !prev)}
              className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-cta transition-colors cursor-pointer"
            >
              {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              {isExpanded ? t('report.competitors.less') : t('report.competitors.details')}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
