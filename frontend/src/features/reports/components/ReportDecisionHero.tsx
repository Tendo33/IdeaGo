import { CircleSlash, Sparkles, TriangleAlert, TrendingUp } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import type { RecommendationType, ResearchReport } from '@/lib/types/research'

function toPercent(value: number | undefined): number {
  const normalized = Number(value)
  if (!Number.isFinite(normalized)) {
    return 0
  }
  return Math.max(0, Math.min(100, Math.round(normalized * 100)))
}

function getDecisionTone(
  recommendationType: RecommendationType,
  t: (key: string, options?: Record<string, unknown>) => string,
): {
  badgeLabel: string
  badgeClass: string
  panelClass: string
  icon: typeof TrendingUp
  title: string
  subtitle: string
} {
  if (recommendationType === 'no_go') {
    return {
      badgeLabel: t('report.header.decision.badge.noGo'),
      badgeClass: 'border-danger/30 bg-danger/10 text-danger',
      panelClass: 'border-danger/20 bg-linear-to-br from-danger/10 via-card to-card',
      icon: CircleSlash,
      title: t('report.header.decision.title.noGo'),
      subtitle: t('report.header.decision.subtitle.noGo'),
    }
  }
  if (recommendationType === 'caution') {
    return {
      badgeLabel: t('report.header.decision.badge.caution'),
      badgeClass: 'border-warning/30 bg-warning/10 text-warning',
      panelClass: 'border-warning/20 bg-linear-to-br from-warning/10 via-card to-card',
      icon: TriangleAlert,
      title: t('report.header.decision.title.caution'),
      subtitle: t('report.header.decision.subtitle.caution'),
    }
  }
  return {
    badgeLabel: t('report.header.decision.badge.go'),
    badgeClass: 'border-cta/30 bg-cta/10 text-cta',
    panelClass: 'border-cta/20 bg-linear-to-br from-cta/10 via-card to-card',
    icon: TrendingUp,
    title: t('report.header.decision.title.go'),
    subtitle: t('report.header.decision.subtitle.go'),
  }
}

function buildSummaryBullets(
  report: ResearchReport,
  t: (key: string, options?: Record<string, unknown>) => string,
): string[] {
  const bullets = [
    report.whitespace_opportunities[0]?.wedge
      ? t('report.header.summary.bestEntryWedge', { value: report.whitespace_opportunities[0].wedge })
      : '',
    report.pain_signals[0]?.theme
      ? t('report.header.summary.mainPain', { value: report.pain_signals[0].theme })
      : '',
    report.commercial_signals[0]?.theme
      ? t('report.header.summary.commercialCue', { value: report.commercial_signals[0].theme })
      : '',
    report.differentiation_angles[0]
      ? t('report.header.summary.executionAngle', { value: report.differentiation_angles[0] })
      : '',
  ]

  return bullets.filter(Boolean).slice(0, 3)
}

interface ReportDecisionHeroProps {
  report: ResearchReport
  keywordText: string
}

export function ReportDecisionHero({ report, keywordText }: ReportDecisionHeroProps) {
  const { t } = useTranslation()
  const decisionTone = useMemo(
    () => getDecisionTone(report.recommendation_type, t),
    [report.recommendation_type, t],
  )
  const summaryBullets = useMemo(() => buildSummaryBullets(report, t), [report, t])
  const opportunityPercent = toPercent(report.opportunity_score?.score)
  const DecisionIcon = decisionTone.icon

  return (
    <section className={`card ${decisionTone.panelClass}`}>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.9fr)]">
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 border px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] ${decisionTone.badgeClass}`}
            >
              <DecisionIcon className="h-3.5 w-3.5" />
              {decisionTone.badgeLabel}
            </span>
            <span className="inline-flex items-center gap-2 border border-border bg-background/85 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5 text-cta" />
              {t('report.header.opportunityScore', { value: opportunityPercent })}
            </span>
          </div>

          <div className="space-y-3">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                {t('report.sections.shouldWeBuildThis')}
              </p>
              <h2 className="mt-2 text-2xl font-bold font-heading text-foreground">
                {decisionTone.title}
              </h2>
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">
              {decisionTone.subtitle}
            </p>
            <p className="text-base leading-relaxed text-foreground break-words">
              {report.go_no_go || report.market_summary}
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="border-2 border-border bg-background/80 p-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                {t('report.header.metrics.painThemes')}
              </p>
              <p className="mt-2 text-2xl font-bold text-foreground">
                {report.pain_signals.length}
              </p>
            </div>
            <div className="border-2 border-border bg-background/80 p-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                {t('report.header.metrics.commercialCues')}
              </p>
              <p className="mt-2 text-2xl font-bold text-foreground">
                {report.commercial_signals.length}
              </p>
            </div>
            <div className="border-2 border-border bg-background/80 p-4">
              <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                {t('report.header.metrics.whitespaceWedges')}
              </p>
              <p className="mt-2 text-2xl font-bold text-foreground">
                {report.whitespace_opportunities.length}
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-col justify-between border-2 border-border bg-background/75 p-5">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              {t('report.header.whyThisCall')}
            </p>
            <div className="mt-4 space-y-3">
              {summaryBullets.length > 0 ? (
                summaryBullets.map(item => (
                  <div
                    key={item}
                    className="border border-border bg-muted/45 px-3 py-3 text-sm text-foreground"
                  >
                    {item}
                  </div>
                ))
              ) : (
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {t('report.header.summary.sparse')}
                </p>
              )}
            </div>
          </div>
          <div className="mt-5 border-t-2 border-border pt-4 text-sm text-muted-foreground">
            <p className="font-semibold text-foreground">{t('report.header.contextKeywords')}</p>
            <p className="mt-2 leading-relaxed break-words">
              {keywordText}
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
