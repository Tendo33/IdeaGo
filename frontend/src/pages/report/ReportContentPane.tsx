import { Suspense, lazy, useMemo, useState, type ReactNode } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { AlertCircle, ArrowUpDown, Info, LayoutGrid, List, RefreshCw, Waves } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { startAnalysis } from '../../api/client'
import { CompetitorCard } from '../../components/CompetitorCard'
import { CompareFloatingBar, ComparePanel } from '../../components/ComparePanel'
import { CompetitorRow } from '../../components/CompetitorRow'
import { ConfidenceCard } from '../../components/ConfidenceCard'
import { EvidenceCostCard } from '../../components/EvidenceCostCard'
import { HeroPanel } from '../../components/HeroPanel'
import { InsightsSection } from '../../components/InsightCard'
import { MarketOverview } from '../../components/MarketOverview'
import { ReportHeader } from '../../components/ReportHeader'
import { SectionNav } from '../../components/SectionNav'
import { VirtualizedCompetitorList } from '../../components/VirtualizedCompetitorList'
import { getCompetitorDomIdFromId, getCompetitorId } from '../../competitor'
import type { Platform, ResearchReport } from '../../types/research'
import { normalizeSourceErrorMessage } from '../../utils/sourceErrorMessage'
import type { SortKey, ViewMode } from './useCompetitorFilters'
import { PLATFORM_OPTIONS, SORT_OPTIONS } from './useCompetitorFilters'
import { broadenQuery } from './query'

const LandscapeChart = lazy(async () => {
  const chartModule = await import('../../components/LandscapeChart')
  return { default: chartModule.LandscapeChart }
})

const SECTION_NAV_ITEMS = (count: number, t: TFunction) => [
  { id: 'section-summary', label: t('report.sections.summary') },
  { id: 'section-landscape', label: t('report.sections.landscape') },
  { id: 'section-competitors', label: t('report.sections.competitors'), count },
  { id: 'section-opportunities', label: t('report.sections.opportunities') },
]
const SECTION_IDS_KEY = 'section-summary|section-landscape|section-competitors|section-opportunities'

const cardStagger = {
  hidden: { opacity: 0, y: 16 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: index * 0.06, duration: 0.4, ease: 'easeOut' as const },
  }),
}
const VIRTUALIZATION_THRESHOLD = 35

function BlueOceanState({ query }: { query: string }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [broadenError, setBroadenError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleBroaden = async () => {
    if (isSubmitting) return
    setIsSubmitting(true)
    setBroadenError(null)
    try {
      const { report_id } = await startAnalysis(broadenQuery(query))
      navigate(`/reports/${report_id}`)
    } catch (error) {
      setBroadenError(error instanceof Error ? error.message : t('report.error.broaden'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="p-10 rounded-2xl bg-card/85 backdrop-blur-xl border border-border/80 text-center shadow-xl"
    >
      <Waves className="w-12 h-12 text-cta mx-auto mb-4" />
      <h3 className="text-xl font-bold font-heading text-text mb-2">{t('report.blueOcean.title')}</h3>
      <p className="text-sm text-text-muted mb-6 max-w-md mx-auto">
        {t('report.blueOcean.description')}
      </p>
      <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
        <button
          onClick={handleBroaden}
          disabled={isSubmitting}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-cta text-primary-foreground text-sm font-semibold cursor-pointer transition-all duration-300 hover:bg-cta-hover hover:-translate-y-0.5 hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-70"
          aria-busy={isSubmitting}
        >
          <RefreshCw className={`w-4 h-4 ${isSubmitting ? 'animate-spin' : ''}`} />
          {isSubmitting ? t('report.blueOcean.tryingBroader') : t('report.blueOcean.tryBroader')}
        </button>
      </div>
      <div className="mt-6 text-left max-w-sm mx-auto">
        <p className="text-xs font-medium text-text-dim mb-2">{t('report.blueOcean.suggestedSteps')}</p>
        <ol className="space-y-1 text-xs text-text-muted list-decimal list-inside">
          <li>{t('report.blueOcean.step1')}</li>
          <li>{t('report.blueOcean.step2')}</li>
          <li>{t('report.blueOcean.step3')}</li>
        </ol>
      </div>
      {broadenError && <p className="mt-4 text-xs text-danger">{broadenError}</p>}
    </motion.div>
  )
}

function AllFailedState({
  sources,
  onRetry,
}: {
  sources: ResearchReport['source_results']
  onRetry: () => void
}) {
  const { t } = useTranslation()
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-8 rounded-2xl bg-card/85 backdrop-blur-xl border border-warning/30 text-center shadow-xl"
    >
      <AlertCircle className="w-10 h-10 text-warning mx-auto mb-3" />
      <h3 className="text-lg font-bold font-heading text-text mb-3">{t('report.failed.title')}</h3>
      <div className="space-y-1.5 mb-5 max-w-sm mx-auto">
        {sources.map(source => (
          <div key={source.platform} className="flex items-center justify-between text-xs">
            <span className="text-text-muted capitalize">{source.platform}</span>
            <span className="text-danger">
              {normalizeSourceErrorMessage(source.status, source.error_msg) ?? source.status}
            </span>
          </div>
        ))}
      </div>
      <p className="text-xs text-text-dim mb-4">{t('report.failed.description')}</p>
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-transparent border border-warning text-warning text-sm font-semibold cursor-pointer transition-all duration-300 hover:bg-warning/10 hover:-translate-y-0.5"
      >
        <RefreshCw className="w-4 h-4" />
        {t('report.failed.retry')}
      </button>
    </motion.div>
  )
}

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
  const reduceMotion = useReducedMotion()
  const shouldAnimateCards = !reduceMotion && filteredCompetitors.length <= 20
  const shouldUseVirtualization =
    filteredCompetitors.length >= VIRTUALIZATION_THRESHOLD
  const sectionNavItems = useMemo(
    () => SECTION_NAV_ITEMS(report.competitors.length, t),
    [report.competitors.length, t],
  )

  const renderCardWrapper = (
    key: string,
    index: number,
    margin: string,
    child: ReactNode,
  ) => {
    if (!shouldAnimateCards) {
      return <div key={key}>{child}</div>
    }
    return (
      <motion.div
        key={key}
        custom={index}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin }}
        variants={cardStagger}
      >
        {child}
      </motion.div>
    )
  }
  return (
    <>
      <ReportHeader report={report} />

      {showReport && !allFailed && (
        <SectionNav sections={sectionNavItems} sectionIdsKey={SECTION_IDS_KEY} />
      )}

      {cancelledMessage && (
        <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-card/85 backdrop-blur-md border border-border/80 mb-6">
          <div className="flex items-center gap-3 min-w-0">
            <Info className="w-5 h-5 text-text-muted shrink-0" />
            <p className="text-sm text-text-muted">{cancelledMessage}</p>
          </div>
          <button
            onClick={onRetryAnalysis}
            className="shrink-0 px-3 py-1.5 text-xs font-medium text-primary-foreground rounded-lg bg-cta hover:bg-cta-hover cursor-pointer transition-colors duration-200"
          >
            {t('report.failed.startAgain')}
          </button>
        </div>
      )}

      <div className={`space-y-10 transition-all duration-500 ${showReport ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
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
              <Suspense fallback={<div data-testid="chart-loading" className="h-64 rounded-xl border border-border bg-bg-card animate-pulse" />}>
                <LandscapeChart competitors={report.competitors} />
              </Suspense>
            )}
          </section>
        )}

        {report.competitors.length > 0 && (
          <section id="section-competitors">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
              <h2 className="text-lg font-semibold font-heading text-text">
                {t('report.competitors.title', { count: filteredCompetitors.length, total: report.competitors.length })}
              </h2>
              <div className="flex flex-wrap items-center gap-2">
                <div className="interactive-surface flex items-center overflow-hidden mr-1">
                  <button
                    onClick={() => setViewMode('grid')}
                    className={`rounded-md p-1.5 cursor-pointer transition-colors ${viewMode === 'grid' ? 'filter-chip-active' : 'text-text-dim hover:text-text'}`}
                    aria-label={t('report.competitors.gridView')}
                  >
                    <LayoutGrid className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setViewMode('list')}
                    className={`rounded-md p-1.5 cursor-pointer transition-colors ${viewMode === 'list' ? 'filter-chip-active' : 'text-text-dim hover:text-text'}`}
                    aria-label={t('report.competitors.listView')}
                  >
                    <List className="w-3.5 h-3.5" />
                  </button>
                </div>

                {PLATFORM_OPTIONS.map(platform => (
                  <button
                    key={platform}
                    onClick={() => togglePlatform(platform)}
                    className={`filter-chip px-2.5 py-1 ${platformFilter.has(platform) ? 'filter-chip-active' : ''}`}
                  >
                    {platform}
                  </button>
                ))}

                <div className="interactive-surface flex items-center gap-1 ml-1 rounded-full px-2 py-1">
                  <ArrowUpDown className="w-3.5 h-3.5 text-text-dim" />
                  <select
                    value={sortBy}
                    onChange={event => setSortBy(event.target.value as SortKey)}
                    className="text-xs bg-transparent text-text-muted border-none outline-none cursor-pointer pr-1"
                  >
                    {SORT_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>
                        {t(`report.sort.${option.value}`)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {shouldUseVirtualization && (
              <p className="text-xs text-text-dim mb-3">
                {t('report.competitors.virtualizedHint')}
              </p>
            )}

            {viewMode === 'grid' && (
              shouldUseVirtualization ? (
                <VirtualizedCompetitorList
                  competitors={filteredCompetitors}
                  allCompetitors={report.competitors}
                  viewMode="grid"
                  compareSet={compareSet}
                  onToggleCompare={toggleCompare}
                />
              ) : (
                <div className="grid gap-4 sm:grid-cols-1 md:grid-cols-2">
                  {filteredCompetitors.map((competitor, index) => {
                    const competitorId = getCompetitorId(competitor)
                    const domId = getCompetitorDomIdFromId(competitorId)
                    const originalIndex = report.competitors.findIndex(c => getCompetitorId(c) === competitorId)
                    return renderCardWrapper(
                        competitorId,
                        index,
                        '-30px',
                        <CompetitorCard
                          competitor={competitor}
                          rank={originalIndex >= 0 ? originalIndex + 1 : index + 1}
                          domId={domId}
                          variant={originalIndex === 0 ? 'featured' : 'standard'}
                          compareSelected={compareSet.has(competitorId)}
                          onToggleCompare={() => toggleCompare(competitorId)}
                        />,
                    )
                  })}
                </div>
              )
            )}

            {viewMode === 'list' && (
              shouldUseVirtualization ? (
                <VirtualizedCompetitorList
                  competitors={filteredCompetitors}
                  allCompetitors={report.competitors}
                  viewMode="list"
                  compareSet={compareSet}
                  onToggleCompare={toggleCompare}
                />
              ) : (
                <div className="space-y-2">
                  {filteredCompetitors.map((competitor, index) => {
                    const competitorId = getCompetitorId(competitor)
                    const domId = getCompetitorDomIdFromId(competitorId)
                    const originalIndex = report.competitors.findIndex(c => getCompetitorId(c) === competitorId)
                    return renderCardWrapper(
                        competitorId,
                        index,
                        '-20px',
                        <CompetitorRow
                          competitor={competitor}
                          rank={originalIndex >= 0 ? originalIndex + 1 : index + 1}
                          domId={domId}
                          compareSelected={compareSet.has(competitorId)}
                          onToggleCompare={() => toggleCompare(competitorId)}
                        />,
                    )
                  })}
                </div>
              )
            )}

            {filteredCompetitors.length === 0 && (
              <p className="text-center text-sm text-text-dim py-6">{t('report.competitors.empty')}</p>
            )}
          </section>
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
