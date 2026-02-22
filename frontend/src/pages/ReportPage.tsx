import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, AlertCircle } from 'lucide-react'
import { useSSE } from '../api/useSSE'
import { getReport } from '../api/client'
import { ProgressTracker } from '../components/ProgressTracker'
import { CompetitorCard } from '../components/CompetitorCard'
import { SourceStatusBar } from '../components/SourceStatusBar'
import { ReportSummary } from '../components/ReportSummary'
import { Skeleton, CompetitorCardSkeleton } from '../components/Skeleton'
import type { ResearchReport } from '../types/research'

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const { events, isComplete, error: sseError } = useSSE(id ?? null)
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    getReport(id)
      .then(setReport)
      .catch(() => {})
  }, [id])

  useEffect(() => {
    if (isComplete && !sseError && id) {
      getReport(id)
        .then(setReport)
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
          <ProgressTracker events={events} />
        )}

        {(sseError || loadError) && (
          <div className="flex items-center gap-3 p-4 rounded-xl bg-danger/10 border border-danger/30 mb-6">
            <AlertCircle className="w-5 h-5 text-danger shrink-0" />
            <p className="text-sm text-danger">{sseError || loadError}</p>
          </div>
        )}

        {report && isComplete && (
          <div className="space-y-8">
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
              <div>
                <h2 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text mb-4">
                  Competitors ({report.competitors.length})
                </h2>
                <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
                  {report.competitors.map((c, i) => (
                    <CompetitorCard key={`${c.name}-${i}`} competitor={c} rank={i + 1} />
                  ))}
                </div>
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
