import { useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { CompetitorCardSkeleton, Skeleton } from '../components/Skeleton'
import { ReportContentPane } from './report/ReportContentPane'
import { ReportErrorBanner } from './report/ReportErrorBanner'
import { ReportProgressPane } from './report/ReportProgressPane'
import { useCompetitorFilters } from './report/useCompetitorFilters'
import { useReportLifecycle } from './report/useReportLifecycle'

export function ReportPage() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const {
    loadPhase,
    report,
    loadError,
    showReport,
    events,
    isComplete,
    isReconnecting,
    sseError,
    cancelled,
    retryCurrentQuery,
    retryErrorState,
    cancelCurrentAnalysis,
  } = useReportLifecycle(id, navigate)

  const {
    sortBy,
    setSortBy,
    platformFilter,
    togglePlatform,
    viewMode,
    setViewMode,
    filteredCompetitors,
    compareSet,
    toggleCompare,
    compareCompetitors,
    showCompare,
    setShowCompare,
    clearCompare,
    setCompareSet,
  } = useCompetitorFilters(report)

  const removeFromCompare = useCallback((name: string) => {
    setCompareSet(previous => {
      const next = new Set(previous)
      next.delete(name)
      if (next.size < 2) {
        setShowCompare(false)
      }
      return next
    })
  }, [setCompareSet, setShowCompare])

  const showProgress = loadPhase === 'processing' || (loadPhase === 'loading' && !report)
  const allFailed = report
    ? report.source_results.length > 0 &&
      report.source_results.every(source => source.status === 'failed' || source.status === 'timeout')
    : false

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="max-w-5xl mx-auto">
        <ReportProgressPane
          show={showProgress}
          events={events}
          isReconnecting={isReconnecting}
          loadPhase={loadPhase}
          isComplete={isComplete}
          reportId={id}
          onCancel={cancelCurrentAnalysis}
        />

        {(sseError || (loadError && !cancelled)) && (
          <ReportErrorBanner message={sseError || loadError || t('report.error.unknown')} onRetry={retryErrorState} />
        )}

        {report && loadPhase === 'ready' && (
          <ReportContentPane
            report={report}
            showReport={showReport}
            allFailed={allFailed}
            filteredCompetitors={filteredCompetitors}
            compareCompetitors={compareCompetitors}
            compareSet={compareSet}
            showCompare={showCompare}
            setShowCompare={setShowCompare}
            clearCompare={clearCompare}
            removeFromCompare={removeFromCompare}
            onRetryAnalysis={retryCurrentQuery}
            sortBy={sortBy}
            setSortBy={setSortBy}
            platformFilter={platformFilter}
            togglePlatform={togglePlatform}
            viewMode={viewMode}
            setViewMode={setViewMode}
            toggleCompare={toggleCompare}
            cancelledMessage={cancelled}
          />
        )}

        {showProgress && isComplete && !report && !sseError && !cancelled && !loadError && (
          <div className="space-y-6">
            <div className="space-y-2">
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-3 w-1/3" />
            </div>
            <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
              {Array.from({ length: 4 }).map((_, index) => (
                <CompetitorCardSkeleton key={index} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
