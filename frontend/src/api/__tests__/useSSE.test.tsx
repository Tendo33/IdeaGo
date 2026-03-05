import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useSSE } from '../useSSE'

vi.mock('../client', () => ({
  getStreamUrl: (id: string) => `/api/v1/reports/${id}/stream`,
  getApiHeaders: () => ({ Authorization: 'Bearer test' })
}))

class MockResponseReader {
  private resolvers: ((value: { done: boolean; value?: Uint8Array }) => void)[] = []
  private chunks: string[] = []
  private closed = false

  read(): Promise<{ done: boolean; value?: Uint8Array }> {
    if (this.chunks.length > 0) {
      const chunk = this.chunks.shift()!
      return Promise.resolve({ done: false, value: new TextEncoder().encode(chunk) })
    }
    if (this.closed) {
      return Promise.resolve({ done: true })
    }
    return new Promise(resolve => {
      this.resolvers.push(resolve)
    })
  }

  emit(eventType: string, payload: unknown) {
    const data = `event: ${eventType}\ndata: ${JSON.stringify(payload)}\n\n`
    if (this.resolvers.length > 0) {
      const resolve = this.resolvers.shift()!
      resolve({ done: false, value: new TextEncoder().encode(data) })
    } else {
      this.chunks.push(data)
    }
  }

  close() {
    this.closed = true
    while (this.resolvers.length > 0) {
      const resolve = this.resolvers.shift()!
      resolve({ done: true })
    }
  }
}

let mockReaders: MockResponseReader[] = []

describe('useSSE', () => {
  beforeEach(() => {
    mockReaders = []
    vi.useRealTimers()
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => {
      const reader = new MockResponseReader()
      mockReaders.push(reader)
      return Promise.resolve({
        ok: true,
        status: 200,
        body: {
          getReader: () => reader
        }
      })
    }))
  })

  it('marks stream complete with cancelled state on cancelled event', async () => {
    const { result } = renderHook(() => useSSE('r1'))

    await waitFor(() => {
      expect(mockReaders).toHaveLength(1)
    })
    const es = mockReaders[0]

    act(() => {
      es.emit('cancelled', {
        type: 'cancelled',
        stage: 'pipeline',
        message: 'Analysis cancelled by user',
        data: {},
        timestamp: new Date().toISOString(),
      })
    })

    await waitFor(() => {
      expect(result.current.isComplete).toBe(true)
      expect(result.current.cancelled).toBe('Analysis cancelled by user')
      expect(result.current.error).toBeNull()
    })
  })

  it('deduplicates replayed events after reconnect', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useSSE('r1'))

    await waitFor(() => {
      expect(mockReaders).toHaveLength(1)
    })
    const first = mockReaders[0]
    const duplicatedEvent = {
        type: 'source_completed',
        stage: 'github_search',
        message: 'Found 3 results from github',
        data: { platform: 'github', count: 3 },
        timestamp: '2026-02-24T14:00:00.000Z',
    }

    act(() => {
      first.emit('source_completed', duplicatedEvent)
      first.close()
    })

    await act(async () => {
      vi.runAllTimers()
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(mockReaders.length).toBeGreaterThanOrEqual(2)
    })
    const second = mockReaders[1]
    
    act(() => {
      second.emit('source_completed', duplicatedEvent)
    })

    await waitFor(() => {
      expect(result.current.events).toHaveLength(1)
    })
  })

  it('ignores stale source listeners after reconnect', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useSSE('r1'))

    await waitFor(() => {
      expect(mockReaders).toHaveLength(1)
    })
    const first = mockReaders[0]

    act(() => {
      first.close()
    })

    await act(async () => {
      vi.runAllTimers()
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(mockReaders.length).toBeGreaterThanOrEqual(2)
    })
    const second = mockReaders[1]

    act(() => {
      first.emit('source_completed', {
        type: 'source_completed',
        stage: 'github_search',
        message: 'Old source event',
        data: { platform: 'github', count: 2 },
        timestamp: '2026-02-24T15:00:00.000Z',
      })
      second.emit('source_completed', {
        type: 'source_completed',
        stage: 'tavily_search',
        message: 'Fresh source event',
        data: { platform: 'tavily', count: 4 },
        timestamp: '2026-02-24T15:00:01.000Z',
      })
    })

    await waitFor(() => {
      expect(result.current.events).toHaveLength(1)
    })
    expect(result.current.events[0]?.stage).toBe('tavily_search')
  })
})
