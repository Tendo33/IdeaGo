import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useSSE } from '../useSSE'

vi.mock('../client', () => ({
  getStreamUrl: (id: string) => `/api/v1/reports/${id}/stream`,
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

  emitWithCRLF(eventType: string, payload: unknown) {
    const data = `event: ${eventType}\r\ndata: ${JSON.stringify(payload)}\r\n\r\n`
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

async function flushMicrotasks() {
  await Promise.resolve()
  await Promise.resolve()
}

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

    await act(async () => {
      await flushMicrotasks()
    })
    expect(mockReaders).toHaveLength(1)
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
      await flushMicrotasks()
      vi.advanceTimersByTime(1000)
      await flushMicrotasks()
    })

    expect(mockReaders.length).toBeGreaterThanOrEqual(2)
    const second = mockReaders[1]

    act(() => {
      second.emit('source_completed', duplicatedEvent)
    })

    await act(async () => {
      await flushMicrotasks()
      vi.advanceTimersByTime(300)
      await flushMicrotasks()
    })
    expect(result.current.events).toHaveLength(1)
  })

  it('parses SSE chunks with CRLF newlines', async () => {
    const { result } = renderHook(() => useSSE('r1'))

    await waitFor(() => {
      expect(mockReaders).toHaveLength(1)
    })
    const reader = mockReaders[0]

    act(() => {
      reader.emitWithCRLF('source_completed', {
        type: 'source_completed',
        stage: 'github_search',
        message: 'Found 3 results from github',
        data: { platform: 'github', count: 3 },
        timestamp: '2026-02-24T14:00:00.000Z',
      })
    })

    await waitFor(() => {
      expect(result.current.events).toHaveLength(1)
      expect(result.current.events[0]?.stage).toBe('github_search')
    })
  })

  it('ignores stale source listeners after reconnect', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useSSE('r1'))

    await act(async () => {
      await flushMicrotasks()
    })
    expect(mockReaders).toHaveLength(1)
    const first = mockReaders[0]

    act(() => {
      first.close()
    })

    await act(async () => {
      await flushMicrotasks()
      vi.advanceTimersByTime(1000)
      await flushMicrotasks()
    })

    expect(mockReaders.length).toBeGreaterThanOrEqual(2)
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

    for (let i = 0; i < 5 && result.current.events.length === 0; i += 1) {
      await act(async () => {
        await flushMicrotasks()
        vi.advanceTimersByTime(300)
        await flushMicrotasks()
      })
    }
    expect(result.current.events).toHaveLength(1)
    expect(result.current.events[0]?.stage).toBe('tavily_search')
  })

  it('keeps reconnecting after repeated transient failures', async () => {
    vi.useFakeTimers()
    const failingFetch = vi.fn().mockRejectedValue(new Error('network down'))
    vi.stubGlobal('fetch', failingFetch)

    const { result } = renderHook(() => useSSE('r1'))

    await act(async () => {
      await flushMicrotasks()
    })

    for (let i = 0; i < 8; i += 1) {
      await act(async () => {
        vi.advanceTimersByTime(15000)
        await flushMicrotasks()
      })
    }

    expect(failingFetch).toHaveBeenCalledTimes(9)
    expect(result.current.error).toBeNull()
    expect(result.current.isComplete).toBe(false)
    expect(result.current.isReconnecting).toBe(true)
  })

  it('treats ping events as recovered connection state', async () => {
    vi.useFakeTimers()
    const { result } = renderHook(() => useSSE('r1'))

    await act(async () => {
      await flushMicrotasks()
    })
    expect(mockReaders).toHaveLength(1)
    const first = mockReaders[0]

    act(() => {
      first.close()
    })

    await act(async () => {
      await flushMicrotasks()
    })
    expect(result.current.isReconnecting).toBe(true)

    await act(async () => {
      vi.advanceTimersByTime(1000)
      await flushMicrotasks()
    })
    expect(mockReaders.length).toBeGreaterThanOrEqual(2)
    const second = mockReaders[1]

    act(() => {
      second.emit('ping', {})
    })

    await act(async () => {
      await flushMicrotasks()
    })
    expect(result.current.isReconnecting).toBe(false)
  })

  it('sanitizes malformed progress payload fields before storing events', async () => {
    const { result } = renderHook(() => useSSE('r1'))

    await waitFor(() => {
      expect(mockReaders).toHaveLength(1)
    })
    const reader = mockReaders[0]

    act(() => {
      reader.emit('intent_parsed', {
        type: 'intent_parsed',
        stage: 'intent',
        message: 'Intent parsed',
        data: {
          app_type: 42,
          keywords: ['legal', 7, null],
          target_scenario: 'contract review',
        },
        timestamp: '2026-02-24T16:00:00.000Z',
      })
      reader.emit('source_completed', {
        type: 'source_completed',
        stage: 'github_search',
        message: 'Found github results',
        data: {
          platform: ['github'],
          count: '3',
        },
        timestamp: '2026-02-24T16:00:01.000Z',
      })
      reader.emit('extraction_completed', {
        type: 'extraction_completed',
        stage: 'extract',
        message: 'Extracted competitors',
        data: {
          count: '2',
        },
        timestamp: '2026-02-24T16:00:02.000Z',
      })
    })

    await waitFor(() => {
      expect(result.current.events).toHaveLength(3)
    })

    expect(result.current.events[0]?.data).toEqual({
      keywords: ['legal'],
      target_scenario: 'contract review',
    })
    expect(result.current.events[1]?.data).toEqual({
      count: 3,
    })
    expect(result.current.events[2]?.data).toEqual({
      count: 2,
    })
  })

  it('preserves query planning families from completed planning events', async () => {
    const { result } = renderHook(() => useSSE('r1'))

    await waitFor(() => {
      expect(mockReaders).toHaveLength(1)
    })
    const reader = mockReaders[0]

    act(() => {
      reader.emit('query_planning_completed', {
        type: 'query_planning_completed',
        stage: 'query_planning',
        message: 'Planned 3 query groups',
        data: {
          count: '3',
          families: ['direct_competitor', 7, 'pain_discovery'],
        },
        timestamp: '2026-02-24T16:05:00.000Z',
      })
    })

    await waitFor(() => {
      expect(result.current.events).toHaveLength(1)
    })

    expect(result.current.events[0]?.data).toEqual({
      count: 3,
      families: ['direct_competitor', 'pain_discovery'],
    })
  })

  it('marks stream complete when report_ready arrives through the parser boundary', async () => {
    const { result } = renderHook(() => useSSE('r1'))

    await waitFor(() => {
      expect(mockReaders).toHaveLength(1)
    })
    const reader = mockReaders[0]

    act(() => {
      reader.emit('report_ready', {
        stage: 'report',
        message: 'Report is ready',
        data: { unexpected: 'value' },
        timestamp: '2026-02-24T16:10:00.000Z',
      })
    })

    await waitFor(() => {
      expect(result.current.isComplete).toBe(true)
    })
    expect(result.current.error).toBeNull()
    expect(result.current.cancelled).toBeNull()
  })

  it('marks stream errored when error arrives through the parser boundary', async () => {
    const { result } = renderHook(() => useSSE('r1'))

    await waitFor(() => {
      expect(mockReaders).toHaveLength(1)
    })
    const reader = mockReaders[0]

    act(() => {
      reader.emit('error', {
        stage: 'pipeline',
        message: 'Pipeline failed',
        data: { count: 'nope' },
        timestamp: '2026-02-24T16:11:00.000Z',
      })
    })

    await waitFor(() => {
      expect(result.current.isComplete).toBe(true)
      expect(result.current.error).toBe('Pipeline failed')
    })
    expect(result.current.cancelled).toBeNull()
  })
})
