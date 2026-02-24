import { useCallback, useEffect, useState } from 'react'
import type { NavigateFunction } from 'react-router-dom'
import { cancelAnalysis, getReportWithStatus, startAnalysis } from '../../api/client'
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

export function useReportLifecycle(id: string | undefined, navigate: NavigateFunction): ReportLifecycleState {
  const [loadPhase, setLoadPhase] = useState<LoadPhase>('loading')
  const [report, setReport] = useState<ResearchReport | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [showReport, setShowReport] = useState(false)

  const { events, isComplete, isReconnecting, error: sseError, cancelled, retry: retrySSE } =
    useSSE(loadPhase === 'processing' ? (id ?? null) : null)

  useEffect(() => {
    if (!id) return
    getReportWithStatus(id)
      .then(result => {
        if (result.status === 'ready') {
          setLoadError(null)
          setReport(result.report)
          setLoadPhase('ready')
          setTimeout(() => setShowReport(true), 100)
          return
        }

        setLoadError(null)
        setShowReport(false)
        setReport(null)
        setLoadPhase('processing')
      })
      .catch(error => {
        setShowReport(false)
        setReport(null)
        setLoadError(error.message)
        setLoadPhase('loading')
      })
  }, [id])

  useEffect(() => {
    if (!id || loadPhase !== 'processing' || !isComplete) return
    if (cancelled || sseError) return

    getReportWithStatus(id)
      .then(result => {
        if (result.status !== 'ready') return
        setReport(result.report)
        setLoadPhase('ready')
        setTimeout(() => setShowReport(true), 100)
      })
      .catch(error => setLoadError(error.message))
  }, [cancelled, id, isComplete, loadPhase, sseError])

  const retryWithQuery = useCallback((query: string | undefined) => {
    if (!query) return

    startAnalysis(query)
      .then(({ report_id }) => navigate(`/reports/${report_id}`))
      .catch(() => {})
  }, [navigate])

  const retryCurrentQuery = useCallback(() => {
    retryWithQuery(report?.query)
  }, [report?.query, retryWithQuery])

  const retryErrorState = useCallback(() => {
    setLoadError(null)
    if (!id) return

    getReportWithStatus(id)
      .then(result => {
        if (result.status === 'ready') {
          setReport(result.report)
          setLoadPhase('ready')
          setShowReport(true)
          return
        }

        setLoadPhase('processing')
        retrySSE()
      })
      .catch(() => retrySSE())
  }, [id, retrySSE])

  const cancelCurrentAnalysis = useCallback(() => {
    if (!id) return
    cancelAnalysis(id).catch(() => {})
  }, [id])

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
