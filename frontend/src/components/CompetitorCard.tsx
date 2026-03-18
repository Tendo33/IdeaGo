import { useState } from 'react'
import { ExternalLink, ThumbsUp, ThumbsDown, DollarSign, ChevronDown, ChevronUp, Github, Globe, Terminal, Smartphone, Flame } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { getCompetitorDomId } from '../competitor'
import { RelevanceRing } from './RelevanceRing'
import type { Competitor } from '../types/research'

const PlatformIcon: Record<string, React.ElementType> = {
  github: Github,
  tavily: Globe,
  producthunt: Flame,
  hackernews: Terminal,
  appstore: Smartphone,
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
      className="inline-flex items-center gap-1.5 text-xs text-cta hover:text-cta-hover transition-colors duration-200 cursor-pointer min-h-[44px] px-2 py-2 -ml-2 rounded-md"
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
      className={`relative bg-card text-card-foreground border transition-all duration-300 ${
        isFeatured
          ? 'border-border shadow-lg p-6 sm:p-8 col-span-1 md:col-span-2 lg:col-span-3 mb-4'
          : 'border-border/50 hover:border-border hover:shadow-md p-5 card-clickable'
      }`}
    >
      {/* Featured Accent Line */}
      {isFeatured && (
        <div className="absolute top-0 left-0 w-full h-1.5 bg-primary" />
      )}
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="text-sm font-mono text-muted-foreground font-bold">{String(rank).padStart(2, '0')}</span>
            {isFeatured && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider bg-foreground text-background">
                {t('report.competitors.top')}
              </span>
            )}
            <h3
              className={`font-black font-heading text-foreground truncate ${isFeatured ? 'text-3xl tracking-tight' : 'text-xl tracking-tight'}`}
              title={competitor.name}
            >
              {competitor.name}
            </h3>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed" title={competitor.one_liner}>
            {competitor.one_liner}
          </p>
        </div>
        <RelevanceRing score={competitor.relevance_score} size={isFeatured ? 48 : 40} />
      </div>

      {/* Feature Tags */}
      {competitor.features.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {competitor.features.slice(0, featuresLimit).map((f, i) => (
            <span key={i} className="inline-flex items-center text-xs text-muted-foreground">
              {f}
              {i < featuresLimit - 1 && <span className="text-border mx-1.5">&bull;</span>}
            </span>
          ))}
          {!isExpanded && competitor.features.length > 4 && (
            <span className="text-xs text-text-dim inline-flex items-center">
              <span className="text-border mx-1.5">&bull;</span>
              +{competitor.features.length - 4} {t('report.competitors.more')}
            </span>
          )}
        </div>
      )}

      {/* Pricing */}
      {competitor.pricing && (
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-medium mb-4">
          <DollarSign className="w-3.5 h-3.5" />
          <span>{competitor.pricing}</span>
        </div>
      )}

      {/* Strengths / Weaknesses */}
      {(isExpanded || isFeatured) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5 pt-4 border-t border-border/40">
          {competitor.strengths.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-success mb-2">
                <ThumbsUp className="w-3 h-3" /> {t('report.competitors.strengths')}
              </div>
              <ul className="space-y-1.5">
                {competitor.strengths.slice(0, prosLimit).map((s, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                    <span className="text-success mt-0.5">&bull;</span> <span>{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {competitor.weaknesses.length > 0 && (
            <div>
              <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-danger mb-2">
                <ThumbsDown className="w-3 h-3" /> {t('report.competitors.weaknesses')}
              </div>
              <ul className="space-y-1.5">
                {competitor.weaknesses.slice(0, consLimit).map((w, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                    <span className="text-danger mt-0.5">&bull;</span> <span>{w}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-border/80 gap-3 flex-wrap sm:flex-nowrap">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex flex-wrap gap-2 shrink-0">
            {competitor.source_platforms.map(p => {
              const Icon = PlatformIcon[p] || Globe
              return (
                <span key={p} className="inline-flex items-center text-text-dim" title={p}>
                  <Icon className="w-4 h-4" />
                  <span className="sr-only">{p}</span>
                </span>
              )
            })}
          </div>
          <div className="flex flex-wrap gap-3">
            {competitor.links.slice(0, isExpanded ? competitor.links.length : 2).map((link, i) => (
              <LinkWithHost key={i} link={link} name={competitor.name} />
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto shrink-0 justify-between sm:justify-end">
          {onToggleCompare && (
            <button
              onClick={e => { e.stopPropagation(); onToggleCompare() }}
              className={`text-xs px-3 min-h-[44px] rounded-md border cursor-pointer transition-all duration-300 ${
                compareSelected
                  ? 'border-cta/50 bg-cta/10 text-cta'
                  : 'border-border/80 text-text-dim hover:border-cta/30 hover:text-text-muted hover:bg-muted/55'
              }`}
              aria-pressed={Boolean(compareSelected)}
            >
              {compareSelected ? t('report.competitors.compareSelected') : t('report.competitors.compareUnselected')}
            </button>
          )}
          {!isFeatured && hasMore && (
            <button
              onClick={() => setIsExpanded(prev => !prev)}
              className="inline-flex items-center gap-1 text-xs text-text-muted hover:text-cta transition-colors cursor-pointer min-h-[44px] px-2 -mr-2 rounded-md"
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
