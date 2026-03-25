import type { ReportListItem } from '@/lib/types/research'

export const HISTORY_CACHE_STORAGE_KEY = 'ideago-history-cache'

export interface HistoryCacheSnapshot {
  pageIndex: number
  hasNextPage: boolean
  reports: ReportListItem[]
}

export function readHistoryCache(): HistoryCacheSnapshot | null {
  if (typeof window === 'undefined') {
    return null
  }

  try {
    const raw = window.sessionStorage.getItem(HISTORY_CACHE_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<HistoryCacheSnapshot>
    if (
      typeof parsed.pageIndex !== 'number' ||
      typeof parsed.hasNextPage !== 'boolean' ||
      !Array.isArray(parsed.reports)
    ) {
      return null
    }
    return {
      pageIndex: parsed.pageIndex,
      hasNextPage: parsed.hasNextPage,
      reports: parsed.reports,
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
