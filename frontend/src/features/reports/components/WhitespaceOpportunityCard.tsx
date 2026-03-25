import { Compass, Sparkles, Target } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { InsightCard } from '@/features/reports/components/InsightCard'
import type { OpportunityScoreBreakdown, WhitespaceOpportunity } from '@/lib/types/research'

export interface WhitespaceOpportunityCardProps {
  opportunities: WhitespaceOpportunity[]
  opportunityScore?: OpportunityScoreBreakdown | null
  differentiationAngles?: string[]
}

function toPercent(value: number | null | undefined): number {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 0
  }
  return Math.max(0, Math.min(100, Math.round(value * 100)))
}

export function WhitespaceOpportunityCard({
  opportunities,
  opportunityScore,
  differentiationAngles = [],
}: WhitespaceOpportunityCardProps) {
  const { t } = useTranslation()
  const visibleOpportunities = opportunities.slice(0, 2)
  const fallbackAngles = differentiationAngles
    .filter(Boolean)
    .slice(0, 2)
    .map((angle, index) => ({
      title: angle,
      description: t('report.whitespace.fallback.description'),
      key: `angle-${index}-${angle}`,
    }))

  if (visibleOpportunities.length === 0 && fallbackAngles.length === 0) {
    return null
  }

  const score = toPercent(opportunityScore?.score)

  return (
    <div className="card h-full space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 border border-border bg-background px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
            <Compass className="h-3.5 w-3.5 text-cta" />
            {t('report.whitespace.badge')}
          </div>
          <h3 className="mt-3 text-lg font-bold font-heading text-foreground">
            {t('report.whitespace.title')}
          </h3>
        </div>
        <div className="border border-border bg-muted/40 px-3 py-2 text-right">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
            {t('report.whitespace.opportunityScore')}
          </p>
          <p className="mt-1 text-lg font-bold text-foreground">{score}%</p>
        </div>
      </div>

      <div className="space-y-4">
        {visibleOpportunities.map((opportunity, index) => (
          <InsightCard
            key={`${opportunity.title}-${index}`}
            index={index}
            eyebrow={opportunity.target_segment || t('report.whitespace.wedge')}
            title={opportunity.title || opportunity.wedge}
            description={opportunity.description || opportunity.wedge}
            supportingPoints={[
              opportunity.wedge
                ? t('report.whitespace.supporting.entryWedge', { value: opportunity.wedge })
                : '',
              opportunity.target_segment
                ? t('report.whitespace.supporting.targetSegment', { value: opportunity.target_segment })
                : '',
              opportunity.supporting_evidence.length > 0
                ? t('report.whitespace.supporting.references', { count: opportunity.supporting_evidence.length })
                : '',
            ]}
            score={opportunity.potential_score}
            scoreLabel={t('report.whitespace.potential')}
            icon={Target}
            tone="success"
          />
        ))}

        {visibleOpportunities.length === 0
          ? fallbackAngles.map((angle, index) => (
              <InsightCard
                key={angle.key}
                index={index}
                eyebrow={t('report.whitespace.fallback.eyebrow')}
                title={angle.title}
                description={angle.description}
                supportingPoints={[t('report.whitespace.fallback.supportingPoint')]}
                icon={Sparkles}
                tone="default"
              />
            ))
          : null}
      </div>
    </div>
  )
}
