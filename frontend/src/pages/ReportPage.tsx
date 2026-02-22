import { useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, AlertCircle, XCircle, ArrowUpDown } from 'lucide-react'
import { useSSE } from '../api/useSSE'
import { getReport, cancelAnalysis } from '../api/client'
import { ProgressTracker } from '../components/ProgressTracker'
import { CompetitorCard } from '../components/CompetitorCard'
import { SourceStatusBar } from '../components/SourceStatusBar'
import { ReportSummary } from '../components/ReportSummary'
import { RelevanceChart } from '../components/RelevanceChart'
import { Skeleton, CompetitorCardSkeleton } from '../components/Skeleton'
import type { ResearchReport, Platform } from '../types/research'

type SortKey = 'relevance' | 'name' | 'sources'
const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'name', label: 'Name' },
  { value: 'sources', label: 'Sources' },
]
const PLATFORM_OPTIONS: Platform[] = ['github', 'tavily', 'hackernews']

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const { events, isComplete, isReconnecting, error: sseError, retry: retrySSE } = useSSE(id ?? null)
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showReport, setShowReport] = useState(false)
  const [sortBy, setSortBy] = useState<SortKey>('relevance')
  const [platformFilter, setPlatformFilter] = useState<Set<Platform>>(new Set())

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

  const togglePlatform = (p: Platform) => {
    setPlatformFilter(prev => {
      const next = new Set(prev)
      if (next.has(p)) next.delete(p)
      else next.add(p)
      return next
    })
  }

  useEffect(() => {
    if (!id) return
    getReport(id)
      .then(setReport)
      .catch(() => {})
  }, [id])

  useEffect(() => {
    if (isComplete && !sseError && id) {
      getReport(id)
        .then(r => {
          setReport(r)
          setTimeout(() => setShowReport(true), 100)
        })
        .catch(e => setLoadError(e.message))
    }
  }, [isComplete, sseError, id])

  const showProgress = !report || !isComplete
  const allFailed = report?.source_results.every(sr => sr.status !== 'ok')

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="max-w-4xl mx-auto">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-cta transition-colors duration-200 mb-6 cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          New search
        </Link>

        {report && (
          <div className="mb-6">
            <h1 className="text-2xl font-bold font-[family-name:var(--font-heading)] text-text mb-1">
              {report.query}
            </h1>
            <p className="text-xs text-text-dim">
              {report.intent.app_type} &middot; {report.intent.keywords_en.join(', ')} &middot; {new Date(report.created_at).toLocaleString()}
            </p>
          </div>
        )}

        {showProgress && (
          <div>
            <ProgressTracker events={events} isReconnecting={isReconnecting} />
            {!isComplete && id && (
              <div className="flex justify-center mt-2">
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

        {(sseError || loadError) && (
          <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-danger/10 border border-danger/30 mb-6">
            <div className="flex items-center gap-3 min-w-0">
              <AlertCircle className="w-5 h-5 text-danger shrink-0" />
              <p className="text-sm text-danger">{sseError || loadError}</p>
            </div>
            <button
              onClick={() => {
                setLoadError(null)
                if (id) {
                  getReport(id)
                    .then(r => {
                      setReport(r)
                      setShowReport(true)
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

        {report && isComplete && (
          <div className={`space-y-8 transition-all duration-500 ${showReport ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
            {report.source_results.length > 0 && (
              <SourceStatusBar sources={report.source_results} />
            )}

            {allFailed && (
              <div className="p-6 rounded-xl bg-warning/10 border border-warning/30 text-center">
                <p className="text-sm text-warning">All data sources failed. No competitor data available. Try again later.</p>
              </div>
            )}

            {!allFailed && <ReportSummary report={report} />}

            {report.competitors.length > 0 && (
              <RelevanceChart competitors={report.competitors} />
            )}

            {report.competitors.length > 0 && (
              <div>
                <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                  <h2 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text">
                    Competitors ({filteredCompetitors.length}/{report.competitors.length})
                  </h2>
                  <div className="flex flex-wrap items-center gap-2">
                    {PLATFORM_OPTIONS.map(p => (
                      <button
                        key={p}
                        onClick={() => togglePlatform(p)}
                        className={`text-xs px-2.5 py-1 rounded-full border cursor-pointer transition-colors duration-150 ${platformFilter.has(p) ? 'border-cta/50 bg-cta/10 text-cta' : 'border-border text-text-dim hover:border-cta/30'}`}
                      >
                        {p}
                      </button>
                    ))}
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
                <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
                  {filteredCompetitors.map((c, i) => (
                    <CompetitorCard key={`${c.name}-${i}`} competitor={c} rank={i + 1} />
                  ))}
                </div>
                {filteredCompetitors.length === 0 && (
                  <p className="text-center text-sm text-text-dim py-6">No competitors match the current filters.</p>
                )}
              </div>
            )}

            {report.competitors.length === 0 && !allFailed && (
              <div className="p-8 rounded-xl bg-cta/5 border border-cta/20 text-center">
                <p className="text-text-muted text-sm">No competitors found. This could be a blue ocean opportunity.</p>
              </div>
            )}
          </div>
        )}

        {isComplete && !report && !sseError && !loadError && (
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
      </div>
    </div>
  )
}
