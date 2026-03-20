import { Check, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/Badge'
import { getCompetitorId } from '../competitor'
import type { Competitor } from '@/lib/types/research'
import { RelevanceRing } from './RelevanceRing'

interface ComparePanelMobileViewProps {
  competitors: Competitor[]
  allFeatures: string[]
  onRemove: (competitorId: string) => void
}

export function ComparePanelMobileView({ competitors, allFeatures, onRemove }: ComparePanelMobileViewProps) {
  const { t } = useTranslation()

  return (
    <div className="block sm:hidden p-4 space-y-6">
      {competitors.map(competitor => {
        const competitorId = getCompetitorId(competitor)
        return (
          <div
            key={competitorId}
            className="rounded-none border-2 border-border bg-card p-4 shadow-[4px_4px_0px_0px_var(--border)] relative"
          >
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
                <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
                  {t('report.compare.relevance')}
                </span>
                <RelevanceRing score={competitor.relevance_score} size={36} />
              </div>
              <div>
                <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                  {t('report.compare.pricing')}
                </span>
                <span className="text-sm font-medium text-foreground">{competitor.pricing ?? '-'}</span>
              </div>
            </div>

            <div className="mb-6">
              <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-2">
                {t('report.compare.description')}
              </span>
              <p className="text-sm text-foreground leading-relaxed">{competitor.one_liner}</p>
            </div>

            {allFeatures.length > 0 && (
              <div className="mb-4">
                <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-2">
                  {t('report.compare.features')}
                </span>
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
              <div className="space-y-3 pt-3 border-t-2 border-border">
                {competitor.strengths.length > 0 && (
                  <div>
                    <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
                      {t('report.compare.strengths')}
                    </span>
                    <ul className="space-y-1.5">
                      {competitor.strengths.map((strength, index) => (
                        <li key={index} className="text-sm text-foreground flex items-start gap-1.5 leading-snug">
                          <span className="text-success mt-0.5 shrink-0">&bull;</span> <span>{strength}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {competitor.weaknesses.length > 0 && (
                  <div>
                    <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
                      {t('report.compare.weaknesses')}
                    </span>
                    <ul className="space-y-1.5">
                      {competitor.weaknesses.map((weakness, index) => (
                        <li key={index} className="text-sm text-foreground flex items-start gap-1.5 leading-snug">
                          <span className="text-danger mt-0.5 shrink-0">&bull;</span> <span>{weakness}</span>
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
  )
}
