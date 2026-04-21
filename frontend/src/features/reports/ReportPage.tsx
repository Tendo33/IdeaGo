import { Suspense, lazy, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { CompetitorCardSkeleton, Skeleton } from '@/components/ui/Skeleton'
import { Alert } from '@/components/ui/Alert'
import { ReportErrorBanner } from '@/features/reports/components/ReportErrorBanner'
import { ReportProgressPane } from '@/features/reports/components/ReportProgressPane'
import { useCompetitorFilters } from '@/features/reports/components/useCompetitorFilters'
import { useReportViewLifecycle } from '@/features/reports/components/useReportViewLifecycle'
import { useReportCreateFlow } from '@/features/reports/components/useReportCreateFlow'
import { useCreateAnalysis } from '@/features/reports/hooks/useCreateAnalysis'

import { useDocumentTitle } from '@/hooks/useDocumentTitle'
import { formatAppDateTime } from '@/lib/utils/dateLocale'

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
  const { t, i18n } = useTranslation()
  const { id: paramId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { createAnalysis, quotaInfo, clearQuotaInfo } = useCreateAnalysis()

  const isNewAnalysis = paramId === 'new'
  const effectiveId = isNewAnalysis ? undefined : paramId
  const searchQuery = new URLSearchParams(location.search).get('q')?.trim() || undefined
  const stateQuery = (location.state as { query?: string } | null)?.query?.trim() || undefined
  const createQuery = searchQuery || stateQuery
  const language = i18n.resolvedLanguage ?? i18n.language
  const createFlow = useReportCreateFlow({
    isEnabled: isNewAnalysis,
    query: createQuery,
    navigate,
    createAnalysis,
    clearQuotaInfo,
  })

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
    reconnectAttempts,
    lastFailureReason,
    isRetryingAnalysis,
    cancelled,
    checkCurrentStatus,
    retrySSE,
    retryCurrentQuery,
    retryErrorState,
    cancelCurrentAnalysis,
  } = useReportViewLifecycle(effectiveId, navigate, { createAnalysis })

  const handleCancel = useCallback(() => {
    if (isNewAnalysis) {
      navigate('/', { replace: true })
      return
    }
    cancelCurrentAnalysis()
  }, [isNewAnalysis, navigate, cancelCurrentAnalysis])

  const handleCreateErrorAction = useCallback(() => {
    createFlow.retry()
  }, [createFlow])

  useDocumentTitle(report ? `${report.query} — IdeaGo` : isNewAnalysis ? t('report.analyzing', 'Analyzing...') + ' — IdeaGo' : 'IdeaGo')


  const quotaExceeded = Boolean(quotaInfo)
  const createError = createFlow.error
  const quotaResetLabel = quotaInfo?.reset_at
    ? formatAppDateTime(quotaInfo.reset_at, language)
    : null
  const loadError = (isNewAnalysis ? createError : null) || lifecycleError
  const hasRecoverableCreateQuery = Boolean(createQuery)
  const hasRestartableReportQuery = Boolean(report?.query || runtimeStatus?.query)
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
  const usesRestartAction =
    !isNewAnalysis &&
    (runtimeStatus?.status === 'failed' ||
      runtimeStatus?.status === 'cancelled' ||
      runtimeStatus?.status === 'not_found' ||
      runtimeStatus?.status === 'complete')
  const sseErrorActions =
    !isNewAnalysis && sseError
      ? [
          { label: t('report.error.retryStream'), onClick: retrySSE },
          { label: t('report.error.checkStatus'), onClick: checkCurrentStatus },
          ...(hasRestartableReportQuery
            ? [{
                label: t('report.failed.startAgain'),
                onClick: retryCurrentQuery,
                disabled: isRetryingAnalysis,
              }]
            : []),
        ]
      : undefined
  const sseErrorDetails = [
    reconnectAttempts > 0
      ? t('report.error.reconnectAttempts', { count: reconnectAttempts })
      : null,
    lastFailureReason && lastFailureReason !== sseError
      ? t('report.error.lastFailureReason', { reason: lastFailureReason })
      : null,
  ].filter((detail): detail is string => Boolean(detail))
  const sseErrorMessage =
    sseError && sseErrorDetails.length > 0
      ? `${sseError}\n${sseErrorDetails.join('\n')}`
      : sseError
  const errorMessage = sseError ? sseErrorMessage : loadError

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
    !hasBlockingError &&
    (loadPhase === 'processing' ||
      (isNewAnalysis &&
        (createFlow.phase === 'creating' || createFlow.phase === 'redirecting')))
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
                {quotaResetLabel
                  ? t('quota.upgradeHintWithReset', { resetAt: quotaResetLabel })
                  : t('quota.upgradeHint', 'You can start another analysis after your quota resets tomorrow.')}
              </p>
              <p className="text-xs text-warning/80 mt-1">
                {t('quota.reviewHistoryHint', 'You can review your saved reports or check your usage details while you wait.')}
              </p>
            </div>
            <div className="flex shrink-0 gap-2">
              <Link
                to="/reports"
                className="inline-flex min-h-[40px] items-center border-2 border-warning px-3 text-xs font-black uppercase tracking-widest text-warning transition-all duration-150 ease-brutal hover:bg-warning/10 active:translate-x-[1px] active:translate-y-[1px]"
              >
                {t('quota.viewHistory', 'View history')}
              </Link>
              <Link
                to="/profile"
                className="inline-flex min-h-[40px] items-center border-2 border-warning px-3 text-xs font-black uppercase tracking-widest text-warning transition-all duration-150 ease-brutal hover:bg-warning/10 active:translate-x-[1px] active:translate-y-[1px]"
              >
                {t('quota.viewUsage', 'View usage')}
              </Link>
            </div>
          </Alert>
        )}

        {!quotaExceeded && (sseError || loadError) && (
          <ReportErrorBanner
            message={errorMessage || t('report.error.unknown')}
            onRetry={errorActionHandler}
            errorKind={
              isNewAnalysis && createError
                ? 'start_failed'
                : sseError
                  ? 'system'
                  : (loadErrorKind ?? 'system')
            }
            runtimeStatus={runtimeStatus}
            actionLabel={errorActionLabel}
            actionDisabled={usesRestartAction && isRetryingAnalysis}
            actions={sseErrorActions}
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
              isRetryingAnalysis={isRetryingAnalysis}
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
