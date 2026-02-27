import { Suspense, lazy, useState } from 'react'
import { motion } from 'framer-motion'
import { AlertCircle, ArrowUpDown, Info, LayoutGrid, List, RefreshCw, Waves } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { startAnalysis } from '../../api/client'
import { CompetitorCard } from '../../components/CompetitorCard'
import { CompareFloatingBar, ComparePanel } from '../../components/ComparePanel'
import { CompetitorRow } from '../../components/CompetitorRow'
import { HeroPanel } from '../../components/HeroPanel'
import { InsightsSection } from '../../components/InsightCard'
import { MarketOverview } from '../../components/MarketOverview'
import { ReportHeader } from '../../components/ReportHeader'
import { SectionNav } from '../../components/SectionNav'
import type { Platform, ResearchReport } from '../../types/research'
import type { SortKey, ViewMode } from './useCompetitorFilters'
import { PLATFORM_OPTIONS, SORT_OPTIONS } from './useCompetitorFilters'
import { broadenQuery } from './query'

const LandscapeChart = lazy(async () => {
  const chartModule = await import('../../components/LandscapeChart')
  return { default: chartModule.LandscapeChart }
})

const SECTION_NAV_ITEMS = (count: number) => [
  { id: 'section-summary', label: 'Summary' },
  { id: 'section-landscape', label: 'Landscape' },
  { id: 'section-competitors', label: 'Competitors', count },
  { id: 'section-opportunities', label: 'Opportunities' },
]

const cardStagger = {
  hidden: { opacity: 0, y: 16 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: index * 0.06, duration: 0.4, ease: 'easeOut' as const },
  }),
}

function getCompetitorKey(competitor: ResearchReport['competitors'][number]): string {
  return competitor.source_urls[0] ?? competitor.links[0] ?? competitor.name
}

function BlueOceanState({ query }: { query: string }) {
  const navigate = useNavigate()
  const [broadenError, setBroadenError] = useState<string | null>(null)

  const handleBroaden = async () => {
    setBroadenError(null)
    try {
      const { report_id } = await startAnalysis(broadenQuery(query))
      navigate(`/reports/${report_id}`)
    } catch (error) {
      setBroadenError(error instanceof Error ? error.message : 'Failed to start broadened analysis.')
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="p-10 rounded-xl bg-cta/5 border border-cta/20 text-center"
    >
      <Waves className="w-12 h-12 text-cta mx-auto mb-4" />
      <h3 className="text-xl font-bold font-[family-name:var(--font-heading)] text-text mb-2">Blue Ocean Detected</h3>
      <p className="text-sm text-text-muted mb-6 max-w-md mx-auto">
        We couldn&apos;t find direct competitors for your idea. This could mean a genuine market gap worth exploring.
      </p>
      <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
        <button
          onClick={handleBroaden}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cta text-white text-sm font-medium cursor-pointer transition-colors hover:bg-cta-hover"
        >
          <RefreshCw className="w-4 h-4" />
          Try with broader keywords
        </button>
      </div>
      <div className="mt-6 text-left max-w-sm mx-auto">
        <p className="text-xs font-medium text-text-dim mb-2">Suggested next steps:</p>
        <ol className="space-y-1 text-xs text-text-muted list-decimal list-inside">
          <li>Validate demand with user interviews</li>
          <li>Search for indirect or adjacent competitors</li>
          <li>Consider why no one has built this yet</li>
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
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-8 rounded-xl bg-warning/10 border border-warning/30 text-center"
    >
      <AlertCircle className="w-10 h-10 text-warning mx-auto mb-3" />
      <h3 className="text-lg font-bold font-[family-name:var(--font-heading)] text-text mb-3">Couldn&apos;t reach data sources</h3>
      <div className="space-y-1.5 mb-5 max-w-sm mx-auto">
        {sources.map(source => (
          <div key={source.platform} className="flex items-center justify-between text-xs">
            <span className="text-text-muted capitalize">{source.platform}</span>
            <span className="text-danger">{source.error_msg ?? source.status}</span>
          </div>
        ))}
      </div>
      <p className="text-xs text-text-dim mb-4">This is usually temporary. Try again in a few minutes.</p>
      <button
        onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-warning text-white text-sm font-medium cursor-pointer transition-colors hover:bg-warning/80"
      >
        <RefreshCw className="w-4 h-4" />
        Retry Analysis
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
  removeFromCompare: (name: string) => void
  onRetryAnalysis: () => void
  sortBy: SortKey
  setSortBy: (sortKey: SortKey) => void
  platformFilter: Set<Platform>
  togglePlatform: (platform: Platform) => void
  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void
  toggleCompare: (name: string) => void
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
  return (
    <>
      <ReportHeader report={report} />

      {showReport && !allFailed && (
        <SectionNav sections={SECTION_NAV_ITEMS(report.competitors.length)} />
      )}

      {cancelledMessage && (
        <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-secondary border border-border mb-6">
          <div className="flex items-center gap-3 min-w-0">
            <Info className="w-5 h-5 text-text-muted shrink-0" />
            <p className="text-sm text-text-muted">{cancelledMessage}</p>
          </div>
          <button
            onClick={onRetryAnalysis}
            className="shrink-0 px-3 py-1.5 text-xs font-medium text-white rounded-lg bg-cta hover:bg-cta-hover cursor-pointer transition-colors duration-200"
          >
            Start Again
          </button>
        </div>
      )}

      <div className={`space-y-10 transition-all duration-500 ${showReport ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
        {allFailed && (
          <AllFailedState sources={report.source_results} onRetry={onRetryAnalysis} />
        )}

        {!allFailed && <HeroPanel report={report} />}

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
              <h2 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text">
                Competitors ({filteredCompetitors.length}/{report.competitors.length})
              </h2>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center rounded-lg border border-border overflow-hidden mr-1">
                  <button
                    onClick={() => setViewMode('grid')}
                    className={`p-1.5 cursor-pointer transition-colors ${viewMode === 'grid' ? 'bg-cta/15 text-cta' : 'text-text-dim hover:text-text-muted'}`}
                    aria-label="Grid view"
                  >
                    <LayoutGrid className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => setViewMode('list')}
                    className={`p-1.5 cursor-pointer transition-colors ${viewMode === 'list' ? 'bg-cta/15 text-cta' : 'text-text-dim hover:text-text-muted'}`}
                    aria-label="List view"
                  >
                    <List className="w-3.5 h-3.5" />
                  </button>
                </div>

                {PLATFORM_OPTIONS.map(platform => (
                  <button
                    key={platform}
                    onClick={() => togglePlatform(platform)}
                    className={`text-xs px-2.5 py-1 rounded-full border cursor-pointer transition-colors duration-150 ${platformFilter.has(platform) ? 'border-cta/50 bg-cta/10 text-cta' : 'border-border text-text-dim hover:border-cta/30'}`}
                  >
                    {platform}
                  </button>
                ))}

                <div className="flex items-center gap-1 ml-1">
                  <ArrowUpDown className="w-3.5 h-3.5 text-text-dim" />
                  <select
                    value={sortBy}
                    onChange={event => setSortBy(event.target.value as SortKey)}
                    className="text-xs bg-transparent text-text-muted border-none outline-none cursor-pointer"
                  >
                    {SORT_OPTIONS.map(option => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            {viewMode === 'grid' && (
              <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
                {filteredCompetitors.map((competitor, index) => (
                  <motion.div
                    key={getCompetitorKey(competitor)}
                    custom={index}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: '-30px' }}
                    variants={cardStagger}
                  >
                    <CompetitorCard
                      competitor={competitor}
                      rank={index + 1}
                      variant={index === 0 ? 'featured' : 'standard'}
                      compareSelected={compareSet.has(competitor.name)}
                      onToggleCompare={() => toggleCompare(competitor.name)}
                    />
                  </motion.div>
                ))}
              </div>
            )}

            {viewMode === 'list' && (
              <div className="space-y-2">
                {filteredCompetitors.map((competitor, index) => (
                  <motion.div
                    key={getCompetitorKey(competitor)}
                    custom={index}
                    initial="hidden"
                    whileInView="visible"
                    viewport={{ once: true, margin: '-20px' }}
                    variants={cardStagger}
                  >
                    <CompetitorRow
                      competitor={competitor}
                      rank={index + 1}
                      compareSelected={compareSet.has(competitor.name)}
                      onToggleCompare={() => toggleCompare(competitor.name)}
                    />
                  </motion.div>
                ))}
              </div>
            )}

            {filteredCompetitors.length === 0 && (
              <p className="text-center text-sm text-text-dim py-6">No competitors match the current filters.</p>
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
