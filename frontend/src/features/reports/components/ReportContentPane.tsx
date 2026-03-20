import { Suspense, lazy, useMemo } from 'react'
import { Info } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { CompareFloatingBar, ComparePanel } from '@/features/reports/components/ComparePanel'
import { ConfidenceCard } from '@/features/reports/components/ConfidenceCard'
import { EvidenceCostCard } from '@/features/reports/components/EvidenceCostCard'
import { HeroPanel } from '@/features/home/components/HeroPanel'
import { InsightsSection } from '@/features/reports/components/InsightCard'
import { MarketOverview } from '@/features/reports/components/MarketOverview'
import { ReportHeader } from '@/features/reports/components/ReportHeader'
import { ReportCompetitorSection } from '@/features/reports/components/ReportCompetitorSection'
import { SectionNav } from '@/features/reports/components/SectionNav'
import { AllFailedState, BlueOceanState } from '@/features/reports/components/ReportStatusStates'
import { getCompetitorId } from '@/features/reports/competitor'
import type { Platform, ResearchReport } from '@/lib/types/research'
import type { SortKey, ViewMode } from './useCompetitorFilters'
import { buttonVariants } from '@/components/ui/Button'

const LandscapeChart = lazy(async () => {
  const chartModule = await import('@/features/reports/components/LandscapeChart')
  return { default: chartModule.LandscapeChart }
})

const SECTION_NAV_ITEMS = (count: number, t: TFunction) => [
  { id: 'section-summary', label: t('report.sections.summary') },
  { id: 'section-landscape', label: t('report.sections.landscape') },
  { id: 'section-competitors', label: t('report.sections.competitors'), count },
  { id: 'section-opportunities', label: t('report.sections.opportunities') },
]
const SECTION_IDS_KEY = 'section-summary|section-landscape|section-competitors|section-opportunities'

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
  sortBy: SortKey
  setSortBy: (sortKey: SortKey) => void
  platformFilter: Set<Platform>
  togglePlatform: (platform: Platform) => void
  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void
  toggleCompare: (competitorId: string) => void
  cancelledMessage: string | null
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

  const sectionNavItems = useMemo(
    () => SECTION_NAV_ITEMS(report.competitors.length, t),
    [report.competitors.length, t],
  )

  return (
    <>
      <ReportHeader report={report} />

      {showReport && !allFailed && (
        <SectionNav sections={sectionNavItems} sectionIdsKey={SECTION_IDS_KEY} />
      )}

      {cancelledMessage && (
        <div className="flex items-center justify-between gap-3 p-4 rounded-none bg-card border-2 border-border mb-6">
          <div className="flex items-center gap-3 min-w-0">
            <Info className="w-5 h-5 text-muted-foreground shrink-0" />
            <p className="text-sm text-muted-foreground">{cancelledMessage}</p>
          </div>
          <button
            onClick={onRetryAnalysis}
            className={buttonVariants({ variant: 'primary', size: 'sm' })}
          >
            {t('report.failed.startAgain')}
          </button>
        </div>
      )}

      <div className={`space-y-12 sm:space-y-16 transition-all duration-500 ${showReport ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
        {allFailed && (
          <AllFailedState sources={report.source_results} onRetry={onRetryAnalysis} />
        )}

        {!allFailed && <HeroPanel report={report} />}
        {!allFailed && (
          <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ConfidenceCard confidence={report.confidence} />
            <EvidenceCostCard
              evidenceSummary={report.evidence_summary}
              costBreakdown={report.cost_breakdown}
              reportMeta={report.report_meta}
            />
          </section>
        )}

        {!allFailed && (report.market_summary || report.competitors.length > 0) && (
          <section id="section-landscape" className="space-y-6">
            <MarketOverview summary={report.market_summary} />
            {report.competitors.length > 0 && (
              <Suspense fallback={<div data-testid="chart-loading" className="h-64 rounded-none border-2 border-border bg-card animate-pulse" />}>
                <LandscapeChart competitors={report.competitors} />
              </Suspense>
            )}
          </section>
        )}

        {report.competitors.length > 0 && (
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
        )}

        {!allFailed && (
          <InsightsSection angles={report.differentiation_angles} />
        )}

        {report.competitors.length === 0 && !allFailed && (
          <BlueOceanState query={report.query} />
        )}
      </div>

      <CompareFloatingBar
        count={compareSet.size}
        onCompare={() => setShowCompare(true)}
        onClear={clearCompare}
      />

      {showCompare && compareCompetitors.length >= 2 && (
        <ComparePanel
          competitors={compareCompetitors}
          onRemove={removeFromCompare}
          onClose={() => setShowCompare(false)}
        />
      )}
    </>
  )
}
