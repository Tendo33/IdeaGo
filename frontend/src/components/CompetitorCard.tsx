import { useState } from 'react'
import { ExternalLink, ThumbsUp, ThumbsDown, Tag, DollarSign, ChevronDown, ChevronUp } from 'lucide-react'
import type { Competitor } from '../types/research'

const platformColors: Record<string, string> = {
  github: 'bg-purple-500/20 text-purple-300',
  tavily: 'bg-blue-500/20 text-blue-300',
  hackernews: 'bg-orange-500/20 text-orange-300',
}

interface CompetitorCardProps {
  competitor: Competitor
  rank: number
}

export function CompetitorCard({ competitor, rank }: CompetitorCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const scorePercent = Math.round(competitor.relevance_score * 100)
  const scoreColor = scorePercent >= 70 ? 'text-cta' : scorePercent >= 40 ? 'text-warning' : 'text-text-dim'

  const featuresLimit = isExpanded ? competitor.features.length : 5
  const prosLimit = isExpanded ? competitor.strengths.length : 3
  const consLimit = isExpanded ? competitor.weaknesses.length : 3
  const hasMore =
    competitor.features.length > 5 ||
    competitor.strengths.length > 3 ||
    competitor.weaknesses.length > 3

  return (
    <div
      onClick={() => setIsExpanded(prev => !prev)}
      className="rounded-xl border border-border bg-bg-card p-5 transition-all duration-200 hover:border-cta/30 hover:shadow-lg hover:shadow-cta/5 cursor-pointer select-none"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-mono text-text-dim">#{rank}</span>
            <h3 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text truncate">{competitor.name}</h3>
          </div>
          <p className="text-sm text-text-muted leading-relaxed">{competitor.one_liner}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-sm font-semibold ${scoreColor}`}>
            {scorePercent}%
          </span>
          {hasMore && (
            isExpanded
              ? <ChevronUp className="w-4 h-4 text-text-dim" />
              : <ChevronDown className="w-4 h-4 text-text-dim" />
          )}
        </div>
      </div>

      {competitor.features.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {competitor.features.slice(0, featuresLimit).map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-secondary/50 text-text-muted">
              <Tag className="w-3 h-3" />{f}
            </span>
          ))}
          {!isExpanded && competitor.features.length > 5 && (
            <span className="text-xs text-text-dim">+{competitor.features.length - 5} more</span>
          )}
        </div>
      )}

      {competitor.pricing && (
        <div className="flex items-center gap-1.5 text-xs text-text-muted mb-3">
          <DollarSign className="w-3.5 h-3.5" />
          <span>{competitor.pricing}</span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 mb-4">
        {competitor.strengths.length > 0 && (
          <div>
            <div className="flex items-center gap-1 text-xs text-cta mb-1">
              <ThumbsUp className="w-3 h-3" /> Strengths
            </div>
            <ul className="space-y-0.5">
              {competitor.strengths.slice(0, prosLimit).map((s, i) => (
                <li key={i} className="text-xs text-text-muted">&#x2022; {s}</li>
              ))}
            </ul>
          </div>
        )}
        {competitor.weaknesses.length > 0 && (
          <div>
            <div className="flex items-center gap-1 text-xs text-danger mb-1">
              <ThumbsDown className="w-3 h-3" /> Weaknesses
            </div>
            <ul className="space-y-0.5">
              {competitor.weaknesses.slice(0, consLimit).map((w, i) => (
                <li key={i} className="text-xs text-text-muted">&#x2022; {w}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-border">
        <div className="flex gap-1.5">
          {competitor.source_platforms.map(p => (
            <span key={p} className={`text-xs px-2 py-0.5 rounded-full ${platformColors[p] || 'bg-secondary/50 text-text-dim'}`}>
              {p}
            </span>
          ))}
        </div>
        <div className="flex flex-wrap gap-1">
          {competitor.links.slice(0, isExpanded ? competitor.links.length : 2).map((link, i) => (
            <a
              key={i}
              href={link}
              target="_blank"
              rel="noopener noreferrer"
              onClick={e => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-xs text-cta hover:text-cta-hover transition-colors duration-200 cursor-pointer min-h-[44px] px-1"
              aria-label={`Open ${competitor.name} link`}
            >
              <ExternalLink className="w-3.5 h-3.5" />
              {(() => { try { return new URL(link).hostname.replace('www.', '').split('.')[0] } catch { return 'link' } })()}
            </a>
          ))}
        </div>
      </div>
    </div>
  )
}
