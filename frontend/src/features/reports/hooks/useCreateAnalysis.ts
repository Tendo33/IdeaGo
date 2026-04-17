import { useCallback, useState } from 'react'
import { getQuotaInfo, isApiError, startAnalysis, type QuotaInfo } from '@/lib/api/client'

export function useCreateAnalysis() {
  const [quotaInfo, setQuotaInfo] = useState<QuotaInfo | null>(null)

  const clearQuotaInfo = useCallback(() => {
    setQuotaInfo(null)
  }, [])

  const createAnalysis = useCallback(
    async (query: string, options?: { signal?: AbortSignal }) => {
      clearQuotaInfo()
      try {
        return await startAnalysis(query, options?.signal ? { signal: options.signal } : undefined)
      } catch (error) {
        if (isApiError(error) && error.is('QUOTA_EXCEEDED')) {
          try {
            setQuotaInfo(await getQuotaInfo())
          } catch {
            setQuotaInfo(null)
          }
        }
        throw error
      }
    },
    [clearQuotaInfo],
  )

  return {
    createAnalysis,
    quotaInfo,
    clearQuotaInfo,
  }
}
