import { Suspense, lazy, useEffect, useMemo, useRef, useState } from 'react'
import { Info } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { CommercialSignalsCard } from '@/features/reports/components/CommercialSignalsCard'
import { CompareFloatingBar } from '@/features/reports/components/CompareFloatingBar'
import { EvidenceCostCard } from '@/features/reports/components/EvidenceCostCard'
import { MarketOverview } from '@/features/reports/components/MarketOverview'
import { PainSignalsCard } from '@/features/reports/components/PainSignalsCard'
import { ReportHeader } from '@/features/reports/components/ReportHeader'
import { SectionNav } from '@/features/reports/components/SectionNav'
import { WhitespaceOpportunityCard } from '@/features/reports/components/WhitespaceOpportunityCard'
import { AllFailedState, BlueOceanState } from '@/features/reports/components/ReportStatusStates'
import { getCompetitorId } from '@/features/reports/competitor'
import type { Platform, ResearchReport } from '@/lib/types/research'
import type { SortKey, ViewMode } from './useCompetitorFilters'
import { buttonVariants } from '@/components/ui/Button'

const LandscapeChart = lazy(async () => {
  const chartModule = await import('@/features/reports/components/LandscapeChart')
  return { default: chartModule.LandscapeChart }
})

const ReportCompetitorSection = lazy(async () => {
  const sectionModule = await import('@/features/reports/components/ReportCompetitorSection')
  return { default: sectionModule.ReportCompetitorSection }
})

const ComparePanel = lazy(async () => {
  const compareModule = await import('@/features/reports/components/ComparePanel')
  return { default: compareModule.ComparePanel }
})

interface ReportContentPaneProps {
  report: ResearchReport
  showReport: boolean
  allFailed: boolean
  filteredCompetitors: ResearchReport['competitors']
  compareCompetitors: ResearchReport['competitors']
  compareSet: Set<string>
  showCompare: boolean
  setShowCompare: (open: boolean) => void
  clearCompare: () => void
  removeFromCompare: (competitorId: string) => void
  onRetryAnalysis: () => void
  isRetryingAnalysis: boolean
  sortBy: SortKey
  setSortBy: (sortKey: SortKey) => void
  platformFilter: Set<Platform>
  togglePlatform: (platform: Platform) => void
  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void
  toggleCompare: (competitorId: string) => void
  cancelledMessage: string | null
}

type SectionNavItem = {
  id: string
  label: string
  count?: number
}

function DeferredLandscapeChart({ competitors }: { competitors: ResearchReport['competitors'] }) {
  const [shouldRender, setShouldRender] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (shouldRender) return
    const idleTimer = window.setTimeout(() => {
      setShouldRender(true)
    }, 0)
    if (typeof IntersectionObserver === 'undefined') {
      return () => window.clearTimeout(idleTimer)
    }
    const node = containerRef.current
    if (!node) return () => window.clearTimeout(idleTimer)
    const observer = new IntersectionObserver(
      entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          setShouldRender(true)
          observer.disconnect()
        }
      },
      { rootMargin: '240px 0px' },
    )
    observer.observe(node)
    return () => {
      window.clearTimeout(idleTimer)
      observer.disconnect()
    }
  }, [shouldRender])

  return (
    <div ref={containerRef}>
      {shouldRender ? (
        <Suspense fallback={<div data-testid="chart-loading" className="h-64 rounded-none border-2 border-border bg-card animate-pulse" />}>
          <LandscapeChart competitors={competitors} />
        </Suspense>
      ) : (
        <div data-testid="chart-loading" className="h-64 rounded-none border-2 border-border bg-card animate-pulse" />
      )}
    </div>
  )
}

export function ReportContentPane({
  report,
  showReport,
  allFailed,
  filteredCompetitors,
  compareCompetitors,
  compareSet,
  showCompare,
  setShowCompare,
  clearCompare,
  removeFromCompare,
  onRetryAnalysis,
  isRetryingAnalysis,
  sortBy,
  setSortBy,
  platformFilter,
  togglePlatform,
  viewMode,
  setViewMode,
  toggleCompare,
  cancelledMessage,
}: ReportContentPaneProps) {
  const { t } = useTranslation()
  const competitorRankById = useMemo(() => {
    const map = new Map<string, number>()
    for (let index = 0; index < report.competitors.length; index += 1) {
      const competitor = report.competitors[index]
      map.set(getCompetitorId(competitor), index + 1)
    }
    return map
  }, [report.competitors])

  const hasWhyNowSection = report.market_summary.length > 0 || report.competitors.length > 0
  const hasCompetitorSection = report.competitors.length > 0

  const sectionNavItems = useMemo(() => {
    const items: SectionNavItem[] = [
      {
        id: 'section-should-we-build-this',
        label: t('report.sections.shouldWeBuildThis'),
      },
    ]

    if (hasWhyNowSection) {
      items.push({
        id: 'section-why-now',
        label: t('report.sections.whyNow'),
      })
    }

    items.push(
      { id: 'section-pain', label: t('report.sections.pain') },
      { id: 'section-whitespace', label: t('report.sections.whitespace') },
    )

    if (hasCompetitorSection) {
      items.push({
        id: 'section-competitors',
        label: t('report.sections.competitors'),
        count: report.competitors.length,
      })
    }

    items.push({
      id: 'section-evidence-confidence',
      label: t('report.sections.evidenceConfidence'),
    })

    return items
  }, [hasCompetitorSection, hasWhyNowSection, report.competitors.length, t])

  const sectionIdsKey = useMemo(
    () => sectionNavItems.map(section => section.id).join('|'),
    [sectionNavItems],
  )

  return (
    <>
      <section id="section-should-we-build-this">
        <ReportHeader report={report} />
      </section>

      {showReport && !allFailed && (
        <SectionNav sections={sectionNavItems} sectionIdsKey={sectionIdsKey} />
      )}

      {cancelledMessage && (
        <div className="flex items-center justify-between gap-3 p-4 rounded-none bg-card border-2 border-border mb-6">
          <div className="flex items-center gap-3 min-w-0">
            <Info className="w-5 h-5 text-muted-foreground shrink-0" />
            <p className="text-sm text-muted-foreground">{cancelledMessage}</p>
          </div>
          <button
            onClick={onRetryAnalysis}
            disabled={isRetryingAnalysis}
            aria-busy={isRetryingAnalysis}
            className={buttonVariants({ variant: 'primary', size: 'sm' })}
          >
            {t('report.failed.startAgain')}
          </button>
        </div>
      )}

      <div className={`space-y-12 sm:space-y-16 transition-all duration-700 ease-out ${showReport ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}>
        {allFailed && (
          <AllFailedState
            sources={report.source_results}
            onRetry={onRetryAnalysis}
            isRetrying={isRetryingAnalysis}
          />
        )}

        {!allFailed && hasWhyNowSection && (
          <section id="section-why-now" className="space-y-6">
            <MarketOverview summary={report.market_summary} />
            {hasCompetitorSection && (
              <DeferredLandscapeChart competitors={report.competitors} />
            )}
          </section>
        )}

        {!allFailed && (
          <section id="section-pain" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PainSignalsCard signals={report.pain_signals} />
            <CommercialSignalsCard signals={report.commercial_signals} />
            {report.pain_signals.length === 0 && report.commercial_signals.length === 0 ? (
              <div className="rounded-none border-2 border-border bg-card p-4 text-sm text-muted-foreground lg:col-span-2">
                {t(
                  'report.sections.painPlaceholder',
                )}
              </div>
            ) : null}
          </section>
        )}

        {!allFailed && (
          <section id="section-whitespace" className="space-y-4">
            <WhitespaceOpportunityCard
              opportunities={report.whitespace_opportunities}
              opportunityScore={report.opportunity_score}
              differentiationAngles={report.differentiation_angles}
            />
            {report.whitespace_opportunities.length === 0 &&
            report.differentiation_angles.length === 0 ? (
              <div className="rounded-none border-2 border-border bg-card p-4 text-sm text-muted-foreground">
                {t(
                  'report.sections.whitespacePlaceholder',
                )}
              </div>
            ) : null}
          </section>
        )}

        {hasCompetitorSection && (
          <Suspense
            fallback={(
              <div
                data-testid="competitor-section-loading"
                className="h-64 rounded-none border-2 border-border bg-card animate-pulse"
              />
            )}
          >
            <ReportCompetitorSection
              allCompetitors={report.competitors}
              filteredCompetitors={filteredCompetitors}
              compareSet={compareSet}
              sortBy={sortBy}
              setSortBy={setSortBy}
              platformFilter={platformFilter}
              togglePlatform={togglePlatform}
              viewMode={viewMode}
              setViewMode={setViewMode}
              toggleCompare={toggleCompare}
              competitorRankById={competitorRankById}
            />
          </Suspense>
        )}

        {!allFailed && (
          <section id="section-evidence-confidence" className="space-y-4">
            <EvidenceCostCard evidenceSummary={report.evidence_summary} />
          </section>
        )}

        {!hasCompetitorSection && !allFailed && (
          <BlueOceanState query={report.query} />
        )}
      </div>

      <CompareFloatingBar
        count={compareSet.size}
        onCompare={() => setShowCompare(true)}
        onClear={clearCompare}
      />

      {showCompare && compareCompetitors.length >= 2 && (
        <Suspense
          fallback={(
            <div
              data-testid="compare-panel-loading"
              className="fixed inset-0 z-50 bg-background/70"
            />
          )}
        >
          <ComparePanel
            competitors={compareCompetitors}
            onRemove={removeFromCompare}
            onClose={() => setShowCompare(false)}
          />
        </Suspense>
      )}
    </>
  )
}
