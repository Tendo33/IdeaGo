import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { NavigateFunction } from 'react-router-dom'
import { isRequestAbortError } from '@/lib/api/client'

export type ReportCreatePhase = 'idle' | 'creating' | 'redirecting'

interface ReportCreateFlowOptions {
  isEnabled: boolean
  query?: string
  navigate: NavigateFunction
  createAnalysis: (
    query: string,
    options?: { signal?: AbortSignal },
  ) => Promise<{ report_id: string }>
  clearQuotaInfo: () => void
}

export function useReportCreateFlow({
  isEnabled,
  query,
  navigate,
  createAnalysis,
  clearQuotaInfo,
}: ReportCreateFlowOptions) {
  const { t } = useTranslation()
  const [phase, setPhase] = useState<ReportCreatePhase>('idle')
  const [error, setError] = useState<string | null>(null)

  const start = useCallback(
    async (signal?: AbortSignal) => {
      if (!query) {
        navigate('/', { replace: true })
        return
      }
      setError(null)
      clearQuotaInfo()
      setPhase('creating')
      try {
        const { report_id } = await createAnalysis(
          query,
          signal ? { signal } : undefined,
        )
        setPhase('redirecting')
        navigate(`/reports/${report_id}`, { replace: true })
      } catch (nextError) {
        if (isRequestAbortError(nextError)) return
        setPhase('idle')
        const message =
          nextError instanceof Error ? nextError.message : t('home.errorStartAnalysis')
        setError(message || t('home.errorStartAnalysis'))
      }
    },
    [clearQuotaInfo, createAnalysis, navigate, query, t],
  )

  useEffect(() => {
    if (!isEnabled) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void start(controller.signal)
    }, 0)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [isEnabled, start])

  return {
    phase: isEnabled ? phase : 'idle',
    error: isEnabled ? error : null,
    retry: () => void start(),
  }
}
