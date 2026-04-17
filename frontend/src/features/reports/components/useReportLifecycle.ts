import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { NavigateFunction } from 'react-router-dom'
import { cancelAnalysis, startAnalysis } from '@/lib/api/client'
import { useSSE } from '@/lib/api/useSSE'
import type { ReportRuntimeStatus, ResearchReport } from '@/lib/types/research'
import {
  useReportStatusResolution,
  type LoadPhase,
  type ReportLoadErrorKind,
} from './useReportStatusResolution'

export type { LoadPhase } from './useReportStatusResolution'

export interface ReportLifecycleState {
  loadPhase: LoadPhase
  report: ResearchReport | null
  loadError: string | null
  loadErrorKind: ReportLoadErrorKind | null
  runtimeStatus: ReportRuntimeStatus | null
  showReport: boolean
  events: ReturnType<typeof useSSE>['events']
  isComplete: boolean
  isReconnecting: boolean
  sseError: string | null
  reconnectAttempts: number
  lastFailureReason: string | null
  isRetryingAnalysis: boolean
  cancelled: string | null
  retrySSE: () => void
  checkCurrentStatus: () => void
  retryCurrentQuery: () => void
  retryErrorState: () => void
  cancelCurrentAnalysis: () => void
}

interface ReportLifecycleOptions {
  createAnalysis?: (query: string) => Promise<{ report_id: string }>
}

export function useReportLifecycle(
  id: string | undefined,
  navigate: NavigateFunction,
  options?: ReportLifecycleOptions,
): ReportLifecycleState {
  const { t } = useTranslation()
  const [isRetryingAnalysis, setIsRetryingAnalysis] = useState(false)
  const restartInFlightRef = useRef(false)
  const createAnalysis = options?.createAnalysis ?? startAnalysis
  const {
    loadPhase,
    report,
    loadError,
    loadErrorKind,
    runtimeStatus,
    showReport,
    retryQuery,
    setSystemError,
    checkCurrentStatus,
    refreshCurrentReport,
    reconcileAfterStreamComplete,
  } = useReportStatusResolution(id)

  const {
    events,
    isComplete,
    isReconnecting,
    error: sseError,
    cancelled: sseCancelled,
    reconnectAttempts = 0,
    lastFailureReason = null,
    retry: retrySSE,
  } = useSSE(loadPhase === 'processing' ? (id ?? null) : null)
  const cancelled =
    runtimeStatus?.status === 'cancelled'
      ? (runtimeStatus.message ?? null)
      : sseCancelled

  useEffect(() => {
    if (!id || loadPhase !== 'processing' || !isComplete) return
    if (cancelled || sseError) return

    const controller = new AbortController()
    reconcileAfterStreamComplete(controller.signal)
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setSystemError(error instanceof Error ? error.message : t('report.error.unavailableStatus'))
      })
    return () => controller.abort()
  }, [cancelled, id, isComplete, loadPhase, reconcileAfterStreamComplete, setSystemError, sseError, t])

  const retryWithQuery = useCallback(
    (query: string | undefined) => {
      if (restartInFlightRef.current) {
        return
      }
      if (!query) {
        navigate('/', { replace: true })
        return
      }

      restartInFlightRef.current = true
      setIsRetryingAnalysis(true)
      createAnalysis(query)
        .then(({ report_id }) => navigate(`/reports/${report_id}`))
        .catch(error => {
          setSystemError(error instanceof Error ? error.message : t('report.error.restart'))
        })
        .finally(() => {
          restartInFlightRef.current = false
          setIsRetryingAnalysis(false)
        })
    },
    [createAnalysis, navigate, setSystemError, t],
  )

  const retryCurrentQuery = useCallback(() => {
    retryWithQuery(report?.query ?? runtimeStatus?.query ?? retryQuery ?? undefined)
  }, [report?.query, retryQuery, retryWithQuery, runtimeStatus?.query])

  const retryErrorState = useCallback(() => {
    if (
      runtimeStatus?.status === 'failed' ||
      runtimeStatus?.status === 'cancelled' ||
      runtimeStatus?.status === 'not_found' ||
      runtimeStatus?.status === 'complete'
    ) {
      retryCurrentQuery()
      return
    }

    refreshCurrentReport({ onProcessing: retrySSE })
  }, [refreshCurrentReport, retryCurrentQuery, retrySSE, runtimeStatus?.status])

  const cancelCurrentAnalysis = useCallback(() => {
    if (!id) return
    cancelAnalysis(id).catch(error => {
      setSystemError(error instanceof Error ? error.message : t('report.error.cancel'))
    })
  }, [id, setSystemError, t])

  return {
    loadPhase,
    report,
    loadError,
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
    retrySSE,
    checkCurrentStatus,
    retryCurrentQuery,
    retryErrorState,
    cancelCurrentAnalysis,
  }
}
