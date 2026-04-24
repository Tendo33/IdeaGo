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
      parsed.pageIndex !== 0 ||
      typeof parsed.hasNextPage !== 'boolean' ||
      typeof parsed.total !== 'number' ||
      !Array.isArray(parsed.reports)
    ) {
      return null
    }
    const storedLimit = typeof parsed.limit === 'number' ? parsed.limit : parsed.reports.length
    const effectiveLimit = typeof limit === 'number' ? limit : storedLimit
    if (storedLimit !== effectiveLimit) {
      return null
    }
    return {
      userId,
      pageIndex: parsed.pageIndex,
      limit: storedLimit,
      hasNextPage: parsed.hasNextPage,
      total: parsed.total,
      reports: parsed.reports as ReportListItem[],
    }
  } catch {
    return null
  }
}

export function writeHistoryCache(snapshot: HistoryCacheSnapshot): void {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.sessionStorage.setItem(HISTORY_CACHE_STORAGE_KEY, JSON.stringify(snapshot))
  } catch {
    // Ignore storage failures so auth/logout flows do not break in restricted browsers.
  }
}

export function clearHistoryCache(): void {
  if (typeof window === 'undefined') {
    return
  }
  try {
    window.sessionStorage.removeItem(HISTORY_CACHE_STORAGE_KEY)
  } catch {
    // Ignore storage failures so auth/logout flows do not break in restricted browsers.
  }
}
