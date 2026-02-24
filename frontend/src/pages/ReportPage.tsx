import { useEffect, useMemo, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { AlertCircle, XCircle, ArrowUpDown, LayoutGrid, List, Tag, Globe, Search, Waves, RefreshCw, Info } from 'lucide-react'
import { useSSE } from '../api/useSSE'
import { getReportWithStatus, cancelAnalysis, startAnalysis } from '../api/client'
import { HorizontalStepper } from '../components/HorizontalStepper'
import { ReportHeader } from '../components/ReportHeader'
import { HeroPanel } from '../components/HeroPanel'
import { MarketOverview } from '../components/MarketOverview'
import { CompetitorCard } from '../components/CompetitorCard'
import { CompetitorRow } from '../components/CompetitorRow'
import { LandscapeChart } from '../components/LandscapeChart'
import { InsightsSection } from '../components/InsightCard'
import { ComparePanel, CompareFloatingBar } from '../components/ComparePanel'
import { SectionNav } from '../components/SectionNav'
import { Skeleton, CompetitorCardSkeleton } from '../components/Skeleton'
import type { ResearchReport, Platform, PipelineEvent } from '../types/research'

type SortKey = 'relevance' | 'name' | 'sources'
type ViewMode = 'grid' | 'list'

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'name', label: 'Name' },
  { value: 'sources', label: 'Sources' },
]
const PLATFORM_OPTIONS: Platform[] = ['github', 'tavily', 'hackernews']

const SECTION_NAV_ITEMS = (count: number) => [
  { id: 'section-summary', label: 'Summary' },
  { id: 'section-landscape', label: 'Landscape' },
  { id: 'section-competitors', label: 'Competitors', count },
  { id: 'section-opportunities', label: 'Opportunities' },
]

/* ----- Progressive Preview During Search ----- */

interface PreviewData {
  appType?: string
  keywords?: string[]
  targetScenario?: string
  sourcePreviews: { platform: string; count: number }[]
  competitorCount?: number
}

function derivePreview(events: PipelineEvent[]): PreviewData {
  const preview: PreviewData = { sourcePreviews: [] }
  for (const e of events) {
    if (e.type === 'intent_parsed') {
      const data = e.data as Record<string, unknown>
      preview.appType = data.app_type as string | undefined
      preview.keywords = data.keywords as string[] | undefined
      preview.targetScenario = data.target_scenario as string | undefined
    }
    if (e.type === 'source_completed') {
      const count = (e.data?.count as number) ?? 0
      const platform = (e.data?.platform as string) ?? e.stage.replace('_search', '')
      preview.sourcePreviews.push({ platform, count })
    }
    if (e.type === 'extraction_completed') {
      const count = e.data?.count as number | undefined
      if (count !== undefined) preview.competitorCount = (preview.competitorCount ?? 0) + count
    }
  }
  return preview
}

function ProgressPreview({ events }: { events: PipelineEvent[] }) {
  const preview = derivePreview(events)
  const hasContent = preview.appType || preview.sourcePreviews.length > 0

  if (!hasContent) return null

  return (
    <div className="max-w-xl mx-auto space-y-3 mt-4">
      {preview.appType && (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
          className="rounded-xl border border-border bg-bg-card p-4"
        >
          <p className="text-xs font-medium text-text-dim mb-2">Idea Profile</p>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-cta/10 text-cta">
              <Globe className="w-3 h-3" />{preview.appType}
            </span>
            {preview.keywords?.map((kw, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-secondary/50 text-text-muted">
                <Tag className="w-3 h-3" />{kw}
              </span>
            ))}
          </div>
          {preview.targetScenario && (
            <p className="text-xs text-text-muted mt-2">{preview.targetScenario}</p>
          )}
        </motion.div>
      )}

      {preview.sourcePreviews.length > 0 && (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="rounded-xl border border-border bg-bg-card p-4"
        >
          <p className="text-xs font-medium text-text-dim mb-2">Search Results</p>
          <div className="space-y-1.5">
            {preview.sourcePreviews.map((sp, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <Search className="w-3 h-3 text-cta" />
                <span className="text-text-muted">
                  Found <span className="font-medium text-text">{sp.count}</span> results from <span className="font-medium text-text capitalize">{sp.platform}</span>
                </span>
              </div>
            ))}
          </div>
          {preview.competitorCount !== undefined && (
            <p className="text-xs text-cta mt-2 font-medium">
              {preview.competitorCount} potential competitors identified
            </p>
          )}
        </motion.div>
      )}
    </div>
  )
}

/* ----- Enhanced Empty States ----- */

function BlueOceanState({ query }: { query: string }) {
  const navigate = useNavigate()

  const handleBroaden = async () => {
    try {
      const { report_id } = await startAnalysis(query)
      navigate(`/reports/${report_id}`)
    } catch { /* handled by error state */ }
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="p-10 rounded-xl bg-cta/5 border border-cta/20 text-center"
    >
      <Waves className="w-12 h-12 text-cta mx-auto mb-4" />
      <h3 className="text-xl font-bold font-[family-name:var(--font-heading)] text-text mb-2">
        Blue Ocean Detected
      </h3>
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
    </motion.div>
  )
}

function AllFailedState({ sources, onRetry }: { sources: ResearchReport['source_results']; onRetry: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="p-8 rounded-xl bg-warning/10 border border-warning/30 text-center"
    >
      <AlertCircle className="w-10 h-10 text-warning mx-auto mb-3" />
      <h3 className="text-lg font-bold font-[family-name:var(--font-heading)] text-text mb-3">
        Couldn&apos;t reach data sources
      </h3>
      <div className="space-y-1.5 mb-5 max-w-sm mx-auto">
        {sources.map(sr => (
          <div key={sr.platform} className="flex items-center justify-between text-xs">
            <span className="text-text-muted capitalize">{sr.platform}</span>
            <span className="text-danger">{sr.error_msg ?? sr.status}</span>
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

/* ----- Main ReportPage ----- */

const cardStagger = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.06, duration: 0.4, ease: 'easeOut' as const },
  }),
}

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loadPhase, setLoadPhase] = useState<'loading' | 'processing' | 'ready'>('loading')
  const { events, isComplete, isReconnecting, error: sseError, cancelled, retry: retrySSE } =
    useSSE(loadPhase === 'processing' ? (id ?? null) : null)
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showReport, setShowReport] = useState(false)
  const [sortBy, setSortBy] = useState<SortKey>('relevance')
  const [platformFilter, setPlatformFilter] = useState<Set<Platform>>(new Set())
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [compareSet, setCompareSet] = useState<Set<string>>(new Set())
  const [showCompare, setShowCompare] = useState(false)

  const filteredCompetitors = useMemo(() => {
    if (!report) return []
    let list = [...report.competitors]
    if (platformFilter.size > 0) {
      list = list.filter(c => c.source_platforms.some(p => platformFilter.has(p)))
    }
    switch (sortBy) {
      case 'name':
        list.sort((a, b) => a.name.localeCompare(b.name))
        break
      case 'sources':
        list.sort((a, b) => b.source_platforms.length - a.source_platforms.length)
        break
      default:
        list.sort((a, b) => b.relevance_score - a.relevance_score)
    }
    return list
  }, [report, sortBy, platformFilter])

  const compareCompetitors = useMemo(() => {
    if (!report) return []
    return report.competitors.filter(c => compareSet.has(c.name))
  }, [report, compareSet])

  const togglePlatform = (p: Platform) => {
    setPlatformFilter(prev => {
      const next = new Set(prev)
      if (next.has(p)) next.delete(p)
      else next.add(p)
      return next
    })
  }

  const toggleCompare = useCallback((name: string) => {
    setCompareSet(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else if (next.size < 4) next.add(name)
      return next
    })
  }, [])

  const handleRetry = useCallback(() => {
    if (!report?.query) return
    startAnalysis(report.query)
      .then(({ report_id }) => navigate(`/reports/${report_id}`))
      .catch(() => {})
  }, [report, navigate])

  useEffect(() => {
    if (!id) return
    getReportWithStatus(id)
      .then(result => {
        if (result.status === 'ready') {
          setLoadError(null)
          setReport(result.report)
          setLoadPhase('ready')
          setTimeout(() => setShowReport(true), 100)
          return
        }
        setLoadError(null)
        setShowReport(false)
        setReport(null)
        setLoadPhase('processing')
      })
      .catch(e => {
        setShowReport(false)
        setReport(null)
        setLoadError(e.message)
        setLoadPhase('loading')
      })
  }, [id])

  useEffect(() => {
    if (!id || loadPhase !== 'processing' || !isComplete) return
    if (cancelled || sseError) return
    getReportWithStatus(id)
      .then(result => {
        if (result.status !== 'ready') return
        setReport(result.report)
        setLoadPhase('ready')
        setTimeout(() => setShowReport(true), 100)
      })
      .catch(e => setLoadError(e.message))
  }, [isComplete, sseError, cancelled, id, loadPhase])

  const showProgress = loadPhase === 'processing' || (loadPhase === 'loading' && !report)
  const allFailed = report ? report.source_results.every(sr => sr.status !== 'ok') : false

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="max-w-5xl mx-auto">

        {/* Header */}
        {report && <ReportHeader report={report} />}

        {/* Section Nav (sticky, appears on scroll) */}
        {report && loadPhase === 'ready' && showReport && !allFailed && (
          <SectionNav sections={SECTION_NAV_ITEMS(report.competitors.length)} />
        )}

        {/* Progress Phase */}
        {showProgress && (
          <div>
            <HorizontalStepper events={events} isReconnecting={isReconnecting} />
            <ProgressPreview events={events} />
            {loadPhase === 'processing' && !isComplete && id && (
              <div className="flex justify-center mt-4">
                <button
                  onClick={() => { cancelAnalysis(id).catch(() => {}) }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-dim rounded-lg border border-border cursor-pointer transition-colors duration-200 hover:text-danger hover:border-danger/30"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Cancel analysis
                </button>
              </div>
            )}
          </div>
        )}

        {/* Error Banner */}
        {(sseError || (loadError && !cancelled)) && (
          <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-danger/10 border border-danger/30 mb-6">
            <div className="flex items-center gap-3 min-w-0">
              <AlertCircle className="w-5 h-5 text-danger shrink-0" />
              <p className="text-sm text-danger">{sseError || loadError}</p>
            </div>
            <button
              onClick={() => {
                setLoadError(null)
                if (id) {
                  getReportWithStatus(id)
                    .then(result => {
                      if (result.status === 'ready') {
                        setReport(result.report)
                        setLoadPhase('ready')
                        setShowReport(true)
                        return
                      }
                      setLoadPhase('processing')
                      retrySSE()
                    })
                    .catch(() => retrySSE())
                }
              }}
              className="shrink-0 px-3 py-1.5 text-xs font-medium text-white rounded-lg bg-danger hover:bg-danger/80 cursor-pointer transition-colors duration-200"
            >
              Retry
            </button>
          </div>
        )}

        {cancelled && (
          <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-secondary border border-border mb-6">
            <div className="flex items-center gap-3 min-w-0">
              <Info className="w-5 h-5 text-text-muted shrink-0" />
              <p className="text-sm text-text-muted">{cancelled}</p>
            </div>
            {report?.query && (
              <button
                onClick={handleRetry}
                className="shrink-0 px-3 py-1.5 text-xs font-medium text-white rounded-lg bg-cta hover:bg-cta-hover cursor-pointer transition-colors duration-200"
              >
                Start Again
              </button>
            )}
          </div>
        )}

        {/* ===== Report Dashboard ===== */}
        {report && loadPhase === 'ready' && (
          <div className={`space-y-10 transition-all duration-500 ${showReport ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>

            {/* All Sources Failed */}
            {allFailed && (
              <AllFailedState sources={report.source_results} onRetry={handleRetry} />
            )}

            {/* ACT 1: The Verdict */}
            {!allFailed && <HeroPanel report={report} />}

            {/* ACT 2: The Landscape */}
            {!allFailed && (report.market_summary || report.competitors.length > 0) && (
              <section id="section-landscape" className="space-y-6">
                <MarketOverview summary={report.market_summary} />
                {report.competitors.length > 0 && (
                  <LandscapeChart competitors={report.competitors} />
                )}
              </section>
            )}

            {/* ACT 3: The Players */}
            {report.competitors.length > 0 && (
              <section id="section-competitors">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <h2 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text">
                    Competitors ({filteredCompetitors.length}/{report.competitors.length})
                  </h2>
                  <div className="flex flex-wrap items-center gap-2">
                    {/* View toggle */}
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

                    {/* Platform filters */}
                    {PLATFORM_OPTIONS.map(p => (
                      <button
                        key={p}
                        onClick={() => togglePlatform(p)}
                        className={`text-xs px-2.5 py-1 rounded-full border cursor-pointer transition-colors duration-150 ${platformFilter.has(p) ? 'border-cta/50 bg-cta/10 text-cta' : 'border-border text-text-dim hover:border-cta/30'}`}
                      >
                        {p}
                      </button>
                    ))}

                    {/* Sort */}
                    <div className="flex items-center gap-1 ml-1">
                      <ArrowUpDown className="w-3.5 h-3.5 text-text-dim" />
                      <select
                        value={sortBy}
                        onChange={e => setSortBy(e.target.value as SortKey)}
                        className="text-xs bg-transparent text-text-muted border-none outline-none cursor-pointer"
                      >
                        {SORT_OPTIONS.map(o => (
                          <option key={o.value} value={o.value}>{o.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>

                {/* Grid View */}
                {viewMode === 'grid' && (
                  <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
                    {filteredCompetitors.map((c, i) => (
                      <motion.div
                        key={`${c.name}-${i}`}
                        custom={i}
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, margin: '-30px' }}
                        variants={cardStagger}
                      >
                        <CompetitorCard
                          competitor={c}
                          rank={i + 1}
                          variant={i === 0 ? 'featured' : 'standard'}
                          compareSelected={compareSet.has(c.name)}
                          onToggleCompare={() => toggleCompare(c.name)}
                        />
                      </motion.div>
                    ))}
                  </div>
                )}

                {/* List View */}
                {viewMode === 'list' && (
                  <div className="space-y-2">
                    {filteredCompetitors.map((c, i) => (
                      <motion.div
                        key={`${c.name}-${i}`}
                        custom={i}
                        initial="hidden"
                        whileInView="visible"
                        viewport={{ once: true, margin: '-20px' }}
                        variants={cardStagger}
                      >
                        <CompetitorRow
                          competitor={c}
                          rank={i + 1}
                          compareSelected={compareSet.has(c.name)}
                          onToggleCompare={() => toggleCompare(c.name)}
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

            {/* ACT 4: Your Edge */}
            {!allFailed && (
              <InsightsSection angles={report.differentiation_angles} />
            )}

            {/* Blue Ocean */}
            {report.competitors.length === 0 && !allFailed && (
              <BlueOceanState query={report.query} />
            )}
          </div>
        )}

        {/* Loading skeleton */}
        {showProgress && isComplete && !report && !sseError && !cancelled && !loadError && (
          <div className="space-y-6">
            <div className="space-y-2">
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </div>
            <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <CompetitorCardSkeleton key={i} />
              ))}
            </div>
          </div>
        )}

        {/* Compare floating bar */}
        <CompareFloatingBar
          count={compareSet.size}
          onCompare={() => setShowCompare(true)}
          onClear={() => setCompareSet(new Set())}
        />

        {/* Compare modal */}
        {showCompare && compareCompetitors.length >= 2 && (
          <ComparePanel
            competitors={compareCompetitors}
            onRemove={name => {
              setCompareSet(prev => {
                const next = new Set(prev)
                next.delete(name)
                if (next.size < 2) setShowCompare(false)
                return next
              })
            }}
            onClose={() => setShowCompare(false)}
          />
        )}
      </div>
    </div>
  )
}
