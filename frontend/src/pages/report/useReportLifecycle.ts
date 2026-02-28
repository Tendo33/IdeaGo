import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { NavigateFunction } from 'react-router-dom'
import { cancelAnalysis, getReportWithStatus, isRequestAbortError, startAnalysis } from '../../api/client'
import { useSSE } from '../../api/useSSE'
import type { ResearchReport } from '../../types/research'

export type LoadPhase = 'loading' | 'processing' | 'ready'

export interface ReportLifecycleState {
  loadPhase: LoadPhase
  report: ResearchReport | null
  loadError: string | null
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

const MISSING_REPORT_ERROR = 'Report not found or expired. Please start a new analysis.'

export function useReportLifecycle(id: string | undefined, navigate: NavigateFunction): ReportLifecycleState {
  const { t } = useTranslation()
  const [loadPhase, setLoadPhase] = useState<LoadPhase>('loading')
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showReport, setShowReport] = useState(false)
  const revealTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { events, isComplete, isReconnecting, error: sseError, cancelled, retry: retrySSE } =
    useSSE(loadPhase === 'processing' ? (id ?? null) : null)

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

  useEffect(() => {
    if (!id) return
    const controller = new AbortController()
    getReportWithStatus(id, { signal: controller.signal })
      .then(result => {
        if (result.status === 'ready') {
          setLoadError(null)
          setReport(result.report)
          setLoadPhase('ready')
          revealReportSoon()
          return
        }

        if (result.status === 'missing') {
          clearRevealTimer()
          setShowReport(false)
          setReport(null)
          setLoadError(MISSING_REPORT_ERROR)
          setLoadPhase('ready')
          return
        }

        setLoadError(null)
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
        setLoadError(error.message)
        setLoadPhase('loading')
      })
    return () => controller.abort()
  }, [clearRevealTimer, id, revealReportSoon])

  useEffect(() => {
    if (!id || loadPhase !== 'processing' || !isComplete) return
    if (cancelled || sseError) return

    const controller = new AbortController()
    getReportWithStatus(id, { signal: controller.signal })
      .then(result => {
        if (result.status !== 'ready') return
        setLoadError(null)
        setReport(result.report)
        setLoadPhase('ready')
        revealReportSoon()
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        setLoadError(error.message)
      })
    return () => controller.abort()
  }, [cancelled, id, isComplete, loadPhase, revealReportSoon, sseError])

  const retryWithQuery = useCallback(
    (query: string | undefined) => {
      if (!query) return

      setLoadError(null)
      startAnalysis(query)
        .then(({ report_id }) => navigate(`/reports/${report_id}`))
        .catch(error => {
          setLoadError(error instanceof Error ? error.message : t('report.error.restart'))
        })
    },
    [navigate, t],
  )

  const retryCurrentQuery = useCallback(() => {
    retryWithQuery(report?.query)
  }, [report?.query, retryWithQuery])

  const retryErrorState = useCallback(() => {
    setLoadError(null)
    if (!id) return

    getReportWithStatus(id)
      .then(result => {
        if (result.status === 'ready') {
          clearRevealTimer()
          setReport(result.report)
          setLoadPhase('ready')
          setShowReport(true)
          return
        }

        if (result.status === 'missing') {
          clearRevealTimer()
          setShowReport(false)
          setReport(null)
          setLoadPhase('ready')
          setLoadError(MISSING_REPORT_ERROR)
          return
        }

        setLoadPhase('processing')
        retrySSE()
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        retrySSE()
      })
  }, [clearRevealTimer, id, retrySSE])

  const cancelCurrentAnalysis = useCallback(() => {
    if (!id) return
    cancelAnalysis(id).catch(error => {
      setLoadError(error instanceof Error ? error.message : t('report.error.cancel'))
    })
  }, [id, t])

  useEffect(() => () => clearRevealTimer(), [clearRevealTimer])

  return {
    loadPhase,
    report,
    loadError,
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
