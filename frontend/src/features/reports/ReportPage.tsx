import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { Crown } from 'lucide-react'
import { CompetitorCardSkeleton, Skeleton } from '@/components/ui/Skeleton'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { isApiError, isRequestAbortError, startAnalysis } from '@/lib/api/client'
import { ReportContentPane } from '@/features/reports/components/ReportContentPane'
import { ReportErrorBanner } from '@/features/reports/components/ReportErrorBanner'
import { ReportProgressPane } from '@/features/reports/components/ReportProgressPane'
import { useCompetitorFilters } from '@/features/reports/components/useCompetitorFilters'
import { useReportLifecycle } from '@/features/reports/components/useReportLifecycle'

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

export function ReportPage() {
  const { t } = useTranslation()
  const { id: paramId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const [createError, setCreateError] = useState<string | null>(null)
  const [quotaExceeded, setQuotaExceeded] = useState(false)

  const isNewAnalysis = paramId === 'new'
  const effectiveId = isNewAnalysis ? undefined : paramId

  useEffect(() => {
    if (!isNewAnalysis) return
    const query = (location.state as { query?: string } | null)?.query
    if (!query) {
      navigate('/', { replace: true })
      return
    }
    const controller = new AbortController()
    startAnalysis(query, { signal: controller.signal })
      .then(({ report_id }) => {
        navigate(`/reports/${report_id}`, { replace: true })
      })
      .catch(e => {
        if (isRequestAbortError(e)) return
        if (isApiError(e) && e.is('QUOTA_EXCEEDED')) {
          setQuotaExceeded(true)
        }
        const msg = e instanceof Error ? e.message : ''
        setCreateError(msg || t('home.errorStartAnalysis'))
      })
    return () => controller.abort()
  }, [isNewAnalysis, location.state, navigate, t])

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

  useDocumentTitle(report ? `${report.query} — IdeaGo` : isNewAnalysis ? t('report.analyzing', 'Analyzing...') + ' — IdeaGo' : 'IdeaGo')


  const loadError = (isNewAnalysis ? createError : null) || lifecycleError

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
  const showProgress =
    !hasBlockingError && (loadPhase === 'processing' || (loadPhase === 'loading' && !report))
  const allFailed = report
    ? report.source_results.length > 0 &&
      report.source_results.every(source => source.status === 'failed' || source.status === 'timeout')
    : false

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="app-shell max-w-5xl">
        <ReportProgressPane
          show={showProgress}
          events={events}
          isReconnecting={isReconnecting}
          loadPhase={loadPhase}
          isComplete={isComplete}
          reportId={effectiveId}
          onCancel={cancelCurrentAnalysis}
        />

        {quotaExceeded && (
          <Alert variant="warning" className="mb-6 items-center">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-bold text-warning">
                {t('quota.exceeded', 'You\'ve reached your monthly analysis limit.')}
              </p>
              <p className="text-xs text-warning/80 mt-1">
                {t('quota.upgradeHint', 'Upgrade to Pro for 100 analyses per month.')}
              </p>
            </div>
            <Link to="/pricing">
              <Button
                size="sm"
                className="ml-3"
              >
                <Crown className="w-4 h-4 mr-1.5" />
                {t('quota.upgradeCta', 'Upgrade')}
              </Button>
            </Link>
          </Alert>
        )}

        {!quotaExceeded && (sseError || loadError) && (
          <ReportErrorBanner
            message={sseError || loadError || t('report.error.unknown')}
            onRetry={retryErrorState}
            errorKind={sseError ? 'system' : (loadErrorKind ?? 'system')}
            runtimeStatus={runtimeStatus}
          />
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
