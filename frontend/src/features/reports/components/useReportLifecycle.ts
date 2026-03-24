import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { NavigateFunction } from 'react-router-dom'
import {
  cancelAnalysis,
  getReportRuntimeStatus,
  getReportWithStatus,
  isRequestAbortError,
  startAnalysis,
} from '@/lib/api/client'
import { useSSE } from '@/lib/api/useSSE'
import type { ReportRuntimeStatus, ResearchReport } from '@/lib/types/research'

export type LoadPhase = 'loading' | 'processing' | 'ready'
export type ReportLoadErrorKind = 'system' | 'runtime'
const COMPLETE_MISSING_POLL_ATTEMPTS = 3
const COMPLETE_MISSING_BASE_DELAY_MS = 250
const COMPLETE_MISSING_MAX_DELAY_MS = 1500

function isAbortSignalError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

function waitWithBackoff(attempt: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return Promise.reject(new DOMException('Aborted', 'AbortError'))
  }

  const delayMs = Math.min(COMPLETE_MISSING_BASE_DELAY_MS * Math.pow(2, attempt), COMPLETE_MISSING_MAX_DELAY_MS)
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', handleAbort)
      resolve()
    }, delayMs)
    const handleAbort = () => {
      clearTimeout(timer)
      signal?.removeEventListener('abort', handleAbort)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal?.addEventListener('abort', handleAbort)
  })
}

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
  cancelled: string | null
  retrySSE: () => void
  retryCurrentQuery: () => void
  retryErrorState: () => void
  cancelCurrentAnalysis: () => void
}

export function useReportLifecycle(id: string | undefined, navigate: NavigateFunction): ReportLifecycleState {
  const { t } = useTranslation()
  const [loadPhase, setLoadPhase] = useState<LoadPhase>('loading')
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadErrorKind, setLoadErrorKind] = useState<ReportLoadErrorKind | null>(null)
  const [runtimeStatus, setRuntimeStatus] = useState<ReportRuntimeStatus | null>(null)
  const [retryQuery, setRetryQuery] = useState<string | null>(null)
  const [showReport, setShowReport] = useState(false)
  const revealTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { events, isComplete, isReconnecting, error: sseError, cancelled: sseCancelled, retry: retrySSE } =
    useSSE(loadPhase === 'processing' ? (id ?? null) : null)
  const cancelled = runtimeStatus?.status === 'cancelled' ? (runtimeStatus.message ?? null) : sseCancelled

  const clearRevealTimer = useCallback(() => {
    if (revealTimerRef.current) {
      clearTimeout(revealTimerRef.current)
      revealTimerRef.current = null
    }
  }, [])

  const revealReportSoon = useCallback(() => {
    clearRevealTimer()
    revealTimerRef.current = setTimeout(() => {
      setShowReport(true)
      revealTimerRef.current = null
    }, 100)
  }, [clearRevealTimer])

  const setReadyReportState = useCallback((nextReport: ResearchReport, reveal: boolean) => {
    setRuntimeStatus(null)
    setLoadError(null)
    setLoadErrorKind(null)
    setReport(nextReport)
    setRetryQuery(nextReport.query)
    setLoadPhase('ready')
    if (reveal) {
      revealReportSoon()
      return
    }
    clearRevealTimer()
    setShowReport(true)
  }, [clearRevealTimer, revealReportSoon])

  const applyRuntimeStatus = useCallback((status: ReportRuntimeStatus) => {
    setRuntimeStatus(status)
    setLoadPhase('ready')

    if (status.status === 'failed') {
      setLoadError(status.message ?? t('report.error.failedStatus'))
      setLoadErrorKind('runtime')
      return
    }

    if (status.status === 'cancelled') {
      setLoadError(status.message ?? t('report.error.cancelledStatus'))
      setLoadErrorKind('runtime')
      return
    }

    if (status.status === 'not_found') {
      setLoadError(status.message ?? t('report.error.notFoundStatus'))
      setLoadErrorKind('runtime')
      return
    }

    setLoadError(t('report.error.unavailableStatus'))
    setLoadErrorKind('system')
  }, [t])

  const resolveMissingReportStatus = useCallback(
    async (reportId: string, signal?: AbortSignal): Promise<void> => {
      const status = await getReportRuntimeStatus(reportId, { signal })
      setRetryQuery(status.query ?? null)
      clearRevealTimer()
      setShowReport(false)
      setReport(null)

      if (status.status === 'processing') {
        setRuntimeStatus(null)
        setLoadError(null)
        setLoadErrorKind(null)
        setLoadPhase('processing')
        return
      }

      applyRuntimeStatus(status)
    },
    [applyRuntimeStatus, clearRevealTimer],
  )

  const resolveMissingAfterComplete = useCallback(
    async (reportId: string, signal?: AbortSignal): Promise<void> => {
      for (let attempt = 0; attempt < COMPLETE_MISSING_POLL_ATTEMPTS; attempt += 1) {
        const status = await getReportRuntimeStatus(reportId, { signal })
        setRetryQuery(status.query ?? null)

        if (status.status === 'processing') {
          if (attempt < COMPLETE_MISSING_POLL_ATTEMPTS - 1) {
            await waitWithBackoff(attempt, signal)
            continue
          }
          setRuntimeStatus(null)
          setLoadError(null)
          setLoadErrorKind(null)
          setLoadPhase('processing')
          return
        }

        if (status.status === 'complete') {
          const refreshed = await getReportWithStatus(reportId, { signal })
          if (refreshed.status === 'ready') {
            setReadyReportState(refreshed.report, true)
            return
          }
          if (attempt < COMPLETE_MISSING_POLL_ATTEMPTS - 1) {
            await waitWithBackoff(attempt, signal)
            continue
          }
          setRuntimeStatus(status)
          setLoadError(t('report.error.unavailableStatus'))
          setLoadErrorKind('system')
          setLoadPhase('ready')
          return
        }

        applyRuntimeStatus(status)
        return
      }
    },
    [applyRuntimeStatus, setReadyReportState, t],
  )

  useEffect(() => {
    if (!id) return
    const controller = new AbortController()
    getReportWithStatus(id, { signal: controller.signal })
      .then(result => {
        if (result.status === 'ready') {
          setReadyReportState(result.report, true)
          return
        }

        if (result.status === 'missing') {
          return resolveMissingReportStatus(id, controller.signal)
        }

        setRuntimeStatus(null)
        setLoadError(null)
        setLoadErrorKind(null)
        clearRevealTimer()
        setShowReport(false)
        setReport(null)
        setLoadPhase('processing')
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        clearRevealTimer()
        setShowReport(false)
        setReport(null)
        setRuntimeStatus(null)
        setLoadError(error instanceof Error ? error.message : t('report.error.unavailableStatus'))
        setLoadErrorKind('system')
        setLoadPhase('ready')
      })
    return () => controller.abort()
  }, [clearRevealTimer, id, resolveMissingReportStatus, setReadyReportState, t])

  useEffect(() => {
    if (!id || loadPhase !== 'processing' || !isComplete) return
    if (cancelled || sseError) return

    const controller = new AbortController()
    getReportWithStatus(id, { signal: controller.signal })
      .then(async result => {
        if (result.status === 'ready') {
          setReadyReportState(result.report, true)
          return
        }

        if (result.status === 'missing') {
          await resolveMissingAfterComplete(id, controller.signal)
        }
      })
      .catch(error => {
        if (isRequestAbortError(error) || isAbortSignalError(error)) return
        setLoadError(error instanceof Error ? error.message : t('report.error.unavailableStatus'))
        setLoadErrorKind('system')
      })
    return () => controller.abort()
  }, [cancelled, id, isComplete, loadPhase, resolveMissingAfterComplete, setReadyReportState, sseError, t])

  const retryWithQuery = useCallback(
    (query: string | undefined) => {
      if (!query) {
        navigate('/', { replace: true })
        return
      }

      setLoadError(null)
      setLoadErrorKind(null)
      setRuntimeStatus(null)
      startAnalysis(query)
        .then(({ report_id }) => navigate(`/reports/${report_id}`))
        .catch(error => {
          setLoadError(error instanceof Error ? error.message : t('report.error.restart'))
          setLoadErrorKind('system')
        })
    },
    [navigate, t],
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

    setLoadError(null)
    setLoadErrorKind(null)
    setRuntimeStatus(null)
    if (!id) return

    getReportWithStatus(id)
      .then(async result => {
        if (result.status === 'ready') {
          setReadyReportState(result.report, false)
          return
        }

        if (result.status === 'missing') {
          await resolveMissingReportStatus(id)
          return
        }

        setLoadPhase('processing')
        retrySSE()
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        setLoadError(error instanceof Error ? error.message : t('report.error.unavailableStatus'))
        setLoadErrorKind('system')
        retrySSE()
      })
  }, [id, resolveMissingReportStatus, retryCurrentQuery, retrySSE, runtimeStatus?.status, setReadyReportState, t])

  const cancelCurrentAnalysis = useCallback(() => {
    if (!id) return
    cancelAnalysis(id).catch(error => {
      setLoadError(error instanceof Error ? error.message : t('report.error.cancel'))
      setLoadErrorKind('system')
    })
  }, [id, t])

  useEffect(() => () => clearRevealTimer(), [clearRevealTimer])

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
    cancelled,
    retrySSE,
    retryCurrentQuery,
    retryErrorState,
    cancelCurrentAnalysis,
  }
}
