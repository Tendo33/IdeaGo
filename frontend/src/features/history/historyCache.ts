import type { ReportListItem } from '@/lib/types/research'

const HISTORY_CACHE_STORAGE_KEY = 'ideago-history-cache'

export interface HistoryCacheSnapshot {
  userId: string
  pageIndex: number
  limit: number
  hasNextPage: boolean
  total: number
  reports: ReportListItem[]
}

export function readHistoryCache(userId: string, limit?: number): HistoryCacheSnapshot | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const raw = window.sessionStorage.getItem(HISTORY_CACHE_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<HistoryCacheSnapshot>
    if (
      parsed.userId !== userId ||
      typeof parsed.pageIndex !== 'number' ||
      typeof parsed.hasNextPage !== 'boolean' ||
      typeof parsed.total !== 'number' ||
      !Array.isArray(parsed.reports)
    ) {
      return null
    }
    const storedLimit = typeof parsed.limit === 'number' ? parsed.limit : parsed.reports.length
    const effectiveLimit = typeof limit === 'number' ? limit : storedLimit
    const normalizedReports = parsed.reports.slice(0, effectiveLimit)
    return {
      userId,
      pageIndex: parsed.pageIndex,
      limit: storedLimit,
      hasNextPage:
        parsed.hasNextPage ||
        parsed.reports.length > normalizedReports.length ||
        parsed.total > normalizedReports.length,
      total: parsed.total,
      reports: normalizedReports,
    }
  } catch {
    return null
  }
}

export function writeHistoryCache(snapshot: HistoryCacheSnapshot): void {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.setItem(HISTORY_CACHE_STORAGE_KEY, JSON.stringify(snapshot))
}

export function clearHistoryCache(): void {
  if (typeof window === 'undefined') {
    return
  }
  window.sessionStorage.removeItem(HISTORY_CACHE_STORAGE_KEY)
}
