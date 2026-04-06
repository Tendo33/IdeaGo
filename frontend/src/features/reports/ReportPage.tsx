import { Suspense, lazy, useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { CompetitorCardSkeleton, Skeleton } from '@/components/ui/Skeleton'
import { Alert } from '@/components/ui/Alert'
import { isApiError, isRequestAbortError, startAnalysis } from '@/lib/api/client'
import { ReportErrorBanner } from '@/features/reports/components/ReportErrorBanner'
import { ReportProgressPane } from '@/features/reports/components/ReportProgressPane'
import { useCompetitorFilters } from '@/features/reports/components/useCompetitorFilters'
import { useReportLifecycle } from '@/features/reports/components/useReportLifecycle'

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

const ReportContentPane = lazy(async () => {
  const module = await import('@/features/reports/components/ReportContentPane')
  return { default: module.ReportContentPane }
})

function ReportContentLoadingFallback() {
  return (
    <div data-testid="report-content-loading" className="space-y-6">
      <div className="space-y-3">
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4 border-2 border-border bg-card p-5">
          <Skeleton className="h-5 w-1/4" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
        <div className="space-y-4 border-2 border-border bg-card p-5">
          <Skeleton className="h-5 w-1/3" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-5/6" />
        </div>
      </div>
    </div>
  )
}

export function ReportPage() {
  const { t } = useTranslation()
  const { id: paramId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const [createError, setCreateError] = useState<string | null>(null)
  const [quotaExceeded, setQuotaExceeded] = useState(false)

  const isNewAnalysis = paramId === 'new'
  const effectiveId = isNewAnalysis ? undefined : paramId
  const searchQuery = new URLSearchParams(location.search).get('q')?.trim() || undefined
  const stateQuery = (location.state as { query?: string } | null)?.query?.trim() || undefined
  const createQuery = searchQuery || stateQuery

  const startQueuedAnalysis = useCallback(
    async (query: string | undefined, signal?: AbortSignal) => {
      if (!query) {
        navigate('/', { replace: true })
        return
      }

      setCreateError(null)
      setQuotaExceeded(false)

      try {
        const { report_id } = await startAnalysis(query, signal ? { signal } : undefined)
        navigate(`/reports/${report_id}`, { replace: true })
      } catch (error) {
        if (isRequestAbortError(error)) return
        if (isApiError(error) && error.is('QUOTA_EXCEEDED')) {
          setQuotaExceeded(true)
        }
        const message = error instanceof Error ? error.message : ''
        setCreateError(message || t('home.errorStartAnalysis'))
      }
    },
    [navigate, t],
  )

  useEffect(() => {
    if (!isNewAnalysis) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void startQueuedAnalysis(createQuery, controller.signal)
    }, 0)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [createQuery, isNewAnalysis, startQueuedAnalysis])

  const {
    loadPhase,
    report,
    loadError: lifecycleError,
    loadErrorKind,
    runtimeStatus,
    showReport,
    events,
    isComplete,
    isReconnecting,
    sseError,
    cancelled,
    retryCurrentQuery,
    retryErrorState,
    cancelCurrentAnalysis,
  } = useReportLifecycle(effectiveId, navigate)

  const handleCancel = useCallback(() => {
    if (isNewAnalysis) {
      navigate('/', { replace: true })
      return
    }
    cancelCurrentAnalysis()
  }, [isNewAnalysis, navigate, cancelCurrentAnalysis])

  const handleCreateErrorAction = useCallback(() => {
    void startQueuedAnalysis(createQuery)
  }, [createQuery, startQueuedAnalysis])

  useDocumentTitle(report ? `${report.query} — IdeaGo` : isNewAnalysis ? t('report.analyzing', 'Analyzing...') + ' — IdeaGo' : 'IdeaGo')


  const loadError = (isNewAnalysis ? createError : null) || lifecycleError
  const hasRecoverableCreateQuery = Boolean(createQuery)
  const usesHomeFallbackCta =
    (isNewAnalysis && createError && !hasRecoverableCreateQuery) ||
    (!isNewAnalysis &&
      runtimeStatus !== null &&
      !runtimeStatus.query &&
      (runtimeStatus.status === 'not_found' ||
        runtimeStatus.status === 'failed' ||
        runtimeStatus.status === 'cancelled' ||
        runtimeStatus.status === 'complete'))
  const errorActionLabel = usesHomeFallbackCta ? t('error.backToHome') : undefined
  const errorActionHandler = isNewAnalysis && createError ? handleCreateErrorAction : retryErrorState

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

  const removeFromCompare = useCallback((competitorId: string) => {
    setCompareSet(previous => {
      const next = new Set(previous)
      next.delete(competitorId)
      if (next.size < 2) {
        setShowCompare(false)
      }
      return next
    })
  }, [setCompareSet, setShowCompare])

  const hasBlockingError = Boolean(sseError || loadError)
  const showExistingReportLoading = !isNewAnalysis && !hasBlockingError && loadPhase === 'loading' && !report
  const showProgress =
    !hasBlockingError && (loadPhase === 'processing' || (isNewAnalysis && loadPhase === 'loading' && !report))
  const allFailed = report
    ? report.source_results.length > 0 &&
      report.source_results.every(source => source.status === 'failed' || source.status === 'timeout')
    : false

  return (
    <div className="app-shell max-w-5xl pt-8 pb-16">
        <ReportProgressPane
          show={showProgress}
          events={events}
          isReconnecting={isReconnecting}
          loadPhase={loadPhase}
          isComplete={isComplete}
          reportId={effectiveId}
          onCancel={handleCancel}
        />

        {quotaExceeded && (
          <Alert variant="warning" className="mb-6 items-center">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-warning">
                {t('quota.exceeded', 'You have reached your daily analysis limit.')}
              </p>
              <p className="text-xs text-warning/80 mt-1">
                {t('quota.upgradeHint', 'You can start another analysis after your quota resets tomorrow.')}
              </p>
            </div>
          </Alert>
        )}

        {!quotaExceeded && (sseError || loadError) && (
          <ReportErrorBanner
            message={sseError || loadError || t('report.error.unknown')}
            onRetry={errorActionHandler}
            errorKind={sseError ? 'system' : (loadErrorKind ?? 'system')}
            runtimeStatus={runtimeStatus}
            actionLabel={errorActionLabel}
          />
        )}

        {report && loadPhase === 'ready' && (
          <Suspense fallback={<ReportContentLoadingFallback />}>
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
          </Suspense>
        )}

        {showExistingReportLoading && (
          <div className="space-y-6">
            <div className="space-y-3">
              <Skeleton className="h-10 w-2/3" />
              <Skeleton className="h-4 w-1/3" />
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-4 border-2 border-border bg-card p-5">
                <Skeleton className="h-5 w-1/4" />
                <Skeleton className="h-20 w-full" />
                <Skeleton className="h-20 w-full" />
              </div>
              <div className="space-y-4 border-2 border-border bg-card p-5">
                <Skeleton className="h-5 w-1/3" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-5/6" />
              </div>
            </div>
          </div>
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
  )
}
