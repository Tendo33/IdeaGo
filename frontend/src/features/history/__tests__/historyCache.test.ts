import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearHistoryCache,
  readHistoryCache,
  writeHistoryCache,
} from '../historyCache'

describe('historyCache', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('returns null when limit changes instead of reusing truncated cached pages', () => {
    writeHistoryCache({
      userId: 'user-1',
      pageIndex: 0,
      limit: 20,
      hasNextPage: true,
      total: 40,
      reports: Array.from({ length: 20 }, (_, index) => ({
        id: `report-${index}`,
        query: `Report ${index}`,
        created_at: '2026-04-01T00:00:00Z',
        competitor_count: 1,
      })),
    })

    expect(readHistoryCache('user-1', 5)).toBeNull()
  })

  it('clears persisted history cache', () => {
    writeHistoryCache({
      userId: 'user-1',
      pageIndex: 0,
      limit: 20,
      hasNextPage: false,
      total: 1,
      reports: [{
        id: 'report-1',
        query: 'Report 1',
        created_at: '2026-04-01T00:00:00Z',
        competitor_count: 1,
      }],
    })

    clearHistoryCache()
    expect(readHistoryCache('user-1', 20)).toBeNull()
  })
})
