import { useCallback, useEffect, useReducer, useRef, type Dispatch } from 'react'
import { useTranslation } from 'react-i18next'
import { getReportRuntimeStatus, getReportWithStatus, isRequestAbortError } from '@/lib/api/client'
import type { ReportRuntimeStatus, ResearchReport } from '@/lib/types/research'

export type LoadPhase = 'loading' | 'processing' | 'ready'
export type ReportLoadErrorKind = 'system' | 'runtime'

const COMPLETE_MISSING_POLL_ATTEMPTS = 3
const COMPLETE_MISSING_BASE_DELAY_MS = 250
const COMPLETE_MISSING_MAX_DELAY_MS = 1500

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

interface ResolutionState {
  loadPhase: LoadPhase
  report: ResearchReport | null
  loadError: string | null
  loadErrorKind: ReportLoadErrorKind | null
  runtimeStatus: ReportRuntimeStatus | null
  retryQuery: string | null
  showReport: boolean
}

type ResolutionAction =
  | { type: 'set_ready_report'; report: ResearchReport; showReport: boolean }
  | { type: 'set_processing'; retryQuery?: string | null }
  | { type: 'set_runtime_status'; status: ReportRuntimeStatus; message: string; kind: ReportLoadErrorKind }
  | { type: 'set_system_error'; message: string }
  | { type: 'clear_errors' }
  | { type: 'set_retry_query'; retryQuery: string | null }

function createInitialState(): ResolutionState {
  return {
    loadPhase: 'loading',
    report: null,
    loadError: null,
    loadErrorKind: null,
    runtimeStatus: null,
    retryQuery: null,
    showReport: false,
  }
}

function resolutionReducer(state: ResolutionState, action: ResolutionAction): ResolutionState {
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
    default:
      return state
  }
}

function useRevealReport(dispatch: Dispatch<ResolutionAction>) {
  const revealTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
  }, [clearRevealTimer, dispatch])

  const setReadyReportState = useCallback((nextReport: ResearchReport, reveal: boolean) => {
    if (reveal) {
      dispatch({ type: 'set_ready_report', report: nextReport, showReport: false })
      revealReportSoon(nextReport)
      return
    }
    clearRevealTimer()
    dispatch({ type: 'set_ready_report', report: nextReport, showReport: true })
  }, [clearRevealTimer, dispatch, revealReportSoon])

  useEffect(() => () => clearRevealTimer(), [clearRevealTimer])

  return {
    clearRevealTimer,
    setReadyReportState,
  }
}

export interface ReportStatusResolutionResult extends ResolutionState {
  retryQuery: string | null
  setSystemError: (message: string) => void
  clearErrors: () => void
  checkCurrentStatus: () => void
  refreshCurrentReport: (options?: { onProcessing?: () => void }) => void
  reconcileAfterStreamComplete: (signal?: AbortSignal) => Promise<void>
}

export function useReportStatusResolution(id: string | undefined): ReportStatusResolutionResult {
  const { t } = useTranslation()
  const [state, dispatch] = useReducer(resolutionReducer, undefined, createInitialState)
  const { clearRevealTimer, setReadyReportState } = useRevealReport(dispatch)

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

  const setSystemError = useCallback((message: string) => {
    clearRevealTimer()
    dispatch({ type: 'set_system_error', message })
  }, [clearRevealTimer])

  const refreshCurrentReport = useCallback((options?: { onProcessing?: () => void }) => {
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
        options?.onProcessing?.()
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        setSystemError(error instanceof Error ? error.message : t('report.error.unavailableStatus'))
        options?.onProcessing?.()
      })
  }, [id, resolveMissingReportStatus, setReadyReportState, setSystemError, t])

  const checkCurrentStatus = useCallback(() => {
    refreshCurrentReport()
  }, [refreshCurrentReport])

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
        setSystemError(error instanceof Error ? error.message : t('report.error.unavailableStatus'))
      })
    return () => controller.abort()
  }, [id, resolveMissingReportStatus, setReadyReportState, setSystemError, t])

  const reconcileAfterStreamComplete = useCallback(async (signal?: AbortSignal) => {
    if (!id) return

    const result = await getReportWithStatus(id, { signal })
    if (result.status === 'ready') {
      setReadyReportState(result.report, true)
      return
    }

    if (result.status === 'missing') {
      await resolveMissingAfterComplete(id, signal)
    }
  }, [id, resolveMissingAfterComplete, setReadyReportState])

  return {
    ...state,
    retryQuery: state.retryQuery,
    setSystemError,
    clearErrors: () => dispatch({ type: 'clear_errors' }),
    checkCurrentStatus,
    refreshCurrentReport,
    reconcileAfterStreamComplete,
  }
}
