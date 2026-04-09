import { useCallback, useEffect, useReducer, useRef } from 'react'
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

interface LifecycleState {
  loadPhase: LoadPhase
  report: ResearchReport | null
  loadError: string | null
  loadErrorKind: ReportLoadErrorKind | null
  runtimeStatus: ReportRuntimeStatus | null
  retryQuery: string | null
  showReport: boolean
  isRetryingAnalysis: boolean
}

type LifecycleAction =
  | { type: 'set_ready_report'; report: ResearchReport; showReport: boolean }
  | { type: 'set_processing'; retryQuery?: string | null }
  | { type: 'set_runtime_status'; status: ReportRuntimeStatus; message: string; kind: ReportLoadErrorKind }
  | { type: 'set_system_error'; message: string }
  | { type: 'clear_errors' }
  | { type: 'set_retry_query'; retryQuery: string | null }
  | { type: 'set_retrying_analysis'; value: boolean }

function createInitialState(): LifecycleState {
  return {
    loadPhase: 'loading',
    report: null,
    loadError: null,
    loadErrorKind: null,
    runtimeStatus: null,
    retryQuery: null,
    showReport: false,
    isRetryingAnalysis: false,
  }
}

function lifecycleReducer(state: LifecycleState, action: LifecycleAction): LifecycleState {
  switch (action.type) {
    case 'set_ready_report':
      return {
        ...state,
        loadPhase: 'ready',
        report: action.report,
        runtimeStatus: null,
        loadError: null,
        loadErrorKind: null,
        retryQuery: action.report.query,
        showReport: action.showReport,
      }
    case 'set_processing':
      return {
        ...state,
        loadPhase: 'processing',
        report: null,
        runtimeStatus: null,
        loadError: null,
        loadErrorKind: null,
        showReport: false,
        retryQuery: action.retryQuery ?? state.retryQuery,
      }
    case 'set_runtime_status':
      return {
        ...state,
        loadPhase: 'ready',
        report: null,
        runtimeStatus: action.status,
        loadError: action.message,
        loadErrorKind: action.kind,
        showReport: false,
      }
    case 'set_system_error':
      return {
        ...state,
        loadPhase: 'ready',
        report: null,
        runtimeStatus: null,
        loadError: action.message,
        loadErrorKind: 'system',
        showReport: false,
      }
    case 'clear_errors':
      return {
        ...state,
        loadError: null,
        loadErrorKind: null,
      }
    case 'set_retry_query':
      return {
        ...state,
        retryQuery: action.retryQuery,
      }
    case 'set_retrying_analysis':
      return {
        ...state,
        isRetryingAnalysis: action.value,
      }
    default:
      return state
  }
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

export function useReportLifecycle(id: string | undefined, navigate: NavigateFunction): ReportLifecycleState {
  const { t } = useTranslation()
  const [state, dispatch] = useReducer(lifecycleReducer, undefined, createInitialState)
  const revealTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const restartInFlightRef = useRef(false)

  const {
    events,
    isComplete,
    isReconnecting,
    error: sseError,
    cancelled: sseCancelled,
    reconnectAttempts = 0,
    lastFailureReason = null,
    retry: retrySSE,
  } = useSSE(state.loadPhase === 'processing' ? (id ?? null) : null)
  const cancelled =
    state.runtimeStatus?.status === 'cancelled'
      ? (state.runtimeStatus.message ?? null)
      : sseCancelled

  const clearRevealTimer = useCallback(() => {
    if (revealTimerRef.current) {
      clearTimeout(revealTimerRef.current)
      revealTimerRef.current = null
    }
  }, [])

  const revealReportSoon = useCallback((report: ResearchReport) => {
    clearRevealTimer()
    revealTimerRef.current = setTimeout(() => {
      dispatch({ type: 'set_ready_report', report, showReport: true })
      revealTimerRef.current = null
    }, 100)
  }, [clearRevealTimer])

  const setReadyReportState = useCallback((nextReport: ResearchReport, reveal: boolean) => {
    if (reveal) {
      dispatch({ type: 'set_ready_report', report: nextReport, showReport: false })
      revealReportSoon(nextReport)
      return
    }
    clearRevealTimer()
    dispatch({ type: 'set_ready_report', report: nextReport, showReport: true })
  }, [clearRevealTimer, revealReportSoon])

  const applyRuntimeStatus = useCallback((status: ReportRuntimeStatus) => {
    if (status.status === 'failed') {
      dispatch({
        type: 'set_runtime_status',
        status,
        message: status.message ?? t('report.error.failedStatus'),
        kind: 'runtime',
      })
      return
    }
    if (status.status === 'cancelled') {
      dispatch({
        type: 'set_runtime_status',
        status,
        message: status.message ?? t('report.error.cancelledStatus'),
        kind: 'runtime',
      })
      return
    }
    if (status.status === 'not_found') {
      dispatch({
        type: 'set_runtime_status',
        status,
        message: status.message ?? t('report.error.notFoundStatus'),
        kind: 'runtime',
      })
      return
    }
    dispatch({
      type: 'set_runtime_status',
      status,
      message: t('report.error.unavailableStatus'),
      kind: 'system',
    })
  }, [t])

  const resolveMissingReportStatus = useCallback(
    async (reportId: string, signal?: AbortSignal): Promise<void> => {
      const status = await getReportRuntimeStatus(reportId, { signal })
      dispatch({ type: 'set_retry_query', retryQuery: status.query ?? null })

      if (status.status === 'processing') {
        dispatch({ type: 'set_processing', retryQuery: status.query ?? null })
        return
      }

      clearRevealTimer()
      applyRuntimeStatus(status)
    },
    [applyRuntimeStatus, clearRevealTimer],
  )

  const resolveMissingAfterComplete = useCallback(
    async (reportId: string, signal?: AbortSignal): Promise<void> => {
      for (let attempt = 0; attempt < COMPLETE_MISSING_POLL_ATTEMPTS; attempt += 1) {
        const status = await getReportRuntimeStatus(reportId, { signal })
        dispatch({ type: 'set_retry_query', retryQuery: status.query ?? null })

        if (status.status === 'processing') {
          if (attempt < COMPLETE_MISSING_POLL_ATTEMPTS - 1) {
            await waitWithBackoff(attempt, signal)
            continue
          }
          dispatch({ type: 'set_processing', retryQuery: status.query ?? null })
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
          dispatch({
            type: 'set_runtime_status',
            status,
            message: t('report.error.unavailableStatus'),
            kind: 'system',
          })
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

        dispatch({ type: 'set_processing' })
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        clearRevealTimer()
        dispatch({
          type: 'set_system_error',
          message: error instanceof Error ? error.message : t('report.error.unavailableStatus'),
        })
      })
    return () => controller.abort()
  }, [clearRevealTimer, id, resolveMissingReportStatus, setReadyReportState, t])

  const checkCurrentStatus = useCallback(() => {
    if (!id) return

    dispatch({ type: 'clear_errors' })

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

        dispatch({ type: 'set_processing' })
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        dispatch({
          type: 'set_system_error',
          message: error instanceof Error ? error.message : t('report.error.unavailableStatus'),
        })
      })
  }, [id, resolveMissingReportStatus, setReadyReportState, t])

  useEffect(() => {
    if (!id || state.loadPhase !== 'processing' || !isComplete) return
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
        dispatch({
          type: 'set_system_error',
          message: error instanceof Error ? error.message : t('report.error.unavailableStatus'),
        })
      })
    return () => controller.abort()
  }, [cancelled, id, isComplete, resolveMissingAfterComplete, setReadyReportState, sseError, state.loadPhase, t])

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
      dispatch({ type: 'set_retrying_analysis', value: true })
      startAnalysis(query)
        .then(({ report_id }) => navigate(`/reports/${report_id}`))
        .catch(error => {
          dispatch({
            type: 'set_system_error',
            message: error instanceof Error ? error.message : t('report.error.restart'),
          })
        })
        .finally(() => {
          restartInFlightRef.current = false
          dispatch({ type: 'set_retrying_analysis', value: false })
        })
    },
    [navigate, t],
  )

  const retryCurrentQuery = useCallback(() => {
    retryWithQuery(state.report?.query ?? state.runtimeStatus?.query ?? state.retryQuery ?? undefined)
  }, [retryWithQuery, state.report?.query, state.retryQuery, state.runtimeStatus?.query])

  const retryErrorState = useCallback(() => {
    if (
      state.runtimeStatus?.status === 'failed' ||
      state.runtimeStatus?.status === 'cancelled' ||
      state.runtimeStatus?.status === 'not_found' ||
      state.runtimeStatus?.status === 'complete'
    ) {
      retryCurrentQuery()
      return
    }

    dispatch({ type: 'clear_errors' })
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

        dispatch({ type: 'set_processing' })
        retrySSE()
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        dispatch({
          type: 'set_system_error',
          message: error instanceof Error ? error.message : t('report.error.unavailableStatus'),
        })
        retrySSE()
      })
  }, [id, resolveMissingReportStatus, retryCurrentQuery, retrySSE, setReadyReportState, state.runtimeStatus?.status, t])

  const cancelCurrentAnalysis = useCallback(() => {
    if (!id) return
    cancelAnalysis(id).catch(error => {
      dispatch({
        type: 'set_system_error',
        message: error instanceof Error ? error.message : t('report.error.cancel'),
      })
    })
  }, [id, t])

  useEffect(() => () => clearRevealTimer(), [clearRevealTimer])

  return {
    loadPhase: state.loadPhase,
    report: state.report,
    loadError: state.loadError,
    loadErrorKind: state.loadErrorKind,
    runtimeStatus: state.runtimeStatus,
    showReport: state.showReport,
    events,
    isComplete,
    isReconnecting,
    sseError,
    reconnectAttempts,
    lastFailureReason,
    isRetryingAnalysis: state.isRetryingAnalysis,
    cancelled,
    retrySSE,
    checkCurrentStatus,
    retryCurrentQuery,
    retryErrorState,
    cancelCurrentAnalysis,
  }
}
