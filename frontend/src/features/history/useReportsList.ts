import { useCallback, useEffect, useRef, useState } from 'react'
import { isRequestAbortError, listReports } from '@/lib/api/client'
import {
  readHistoryCache,
  writeHistoryCache,
  type HistoryCacheSnapshot,
} from '@/features/history/historyCache'
import type { ReportListItem } from '@/lib/types/research'

interface UseReportsListOptions {
  userId: string
  limit: number
  pageIndex?: number
  query?: string
}

interface UseReportsListResult {
  reports: ReportListItem[]
  total: number
  hasNextPage: boolean
  loading: boolean
  error: string | null
  seededCache: HistoryCacheSnapshot | null | undefined
  refresh: (options?: { signal?: AbortSignal; invalidateCache?: boolean }) => Promise<void>
}

export function useReportsList({
  userId,
  limit,
  pageIndex = 0,
  query = '',
}: UseReportsListOptions): UseReportsListResult {
  const normalizedQuery = query.trim()
  const [seededCache, setSeededCache] = useState<HistoryCacheSnapshot | null | undefined>(undefined)
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [total, setTotal] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const seededCacheRef = useRef<HistoryCacheSnapshot | null | undefined>(undefined)

  const refresh = useCallback(async (options?: { signal?: AbortSignal; invalidateCache?: boolean }) => {
    if (!userId) return
    const signal = options?.signal
    const invalidateCache = options?.invalidateCache === true

    const shouldUseCache = pageIndex === 0 && normalizedQuery.length === 0
    if (invalidateCache) {
      seededCacheRef.current = null
      setSeededCache(null)
    }
    if (!(shouldUseCache && seededCacheRef.current) || invalidateCache) {
      setLoading(true)
    }

    try {
      const response = await listReports({
        limit,
        offset: pageIndex * limit,
        q: normalizedQuery,
        signal,
      })
      setReports(response.items)
      setHasNextPage(response.has_next)
      setTotal(response.total)
      setError(null)
      if (shouldUseCache) {
        const nextCache = {
          userId,
          pageIndex,
          limit,
          hasNextPage: response.has_next,
          total: response.total,
          reports: response.items,
        }
        seededCacheRef.current = nextCache
        setSeededCache(nextCache)
        writeHistoryCache({
          ...nextCache,
        })
      }
    } catch (nextError) {
      if (isRequestAbortError(nextError)) return
      setError(nextError instanceof Error ? nextError.message : 'Failed to load reports')
    } finally {
      if (!signal?.aborted) {
        setLoading(false)
      }
    }
  }, [limit, normalizedQuery, pageIndex, userId])

  useEffect(() => {
    if (!userId) {
      seededCacheRef.current = null
      setSeededCache(null)
      setReports([])
      setTotal(0)
      setHasNextPage(false)
      setLoading(false)
      return
    }

    const shouldUseCache = pageIndex === 0 && normalizedQuery.length === 0
    const cache = shouldUseCache ? readHistoryCache(userId, limit) : null
    seededCacheRef.current = cache
    setSeededCache(cache)
    setReports(cache?.reports ?? [])
    setTotal(cache?.total ?? 0)
    setHasNextPage(cache?.hasNextPage ?? false)
    setLoading(cache === null)
    setError(null)
    const controller = new AbortController()
    void refresh({ signal: controller.signal })
    return () => controller.abort()
  }, [limit, normalizedQuery, pageIndex, refresh, userId])

  return {
    reports,
    total,
    hasNextPage,
    loading,
    error,
    seededCache,
    refresh,
  }
}
