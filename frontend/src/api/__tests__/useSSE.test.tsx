import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useSSE } from '../useSSE'

vi.mock('../client', () => ({
  getStreamUrl: (id: string) => `/api/v1/reports/${id}/stream`,
}))

type EventHandler = (event: MessageEvent) => void

class MockEventSource {
  static instances: MockEventSource[] = []

  readonly url: string
  readonly listeners = new Map<string, Set<EventHandler>>()
  onerror: (() => void) | null = null
  close = vi.fn()

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, handler: EventHandler) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type)!.add(handler)
  }

  emit(type: string, payload: Record<string, unknown>) {
    const handlers = this.listeners.get(type)
    if (!handlers) return
    const event = { data: JSON.stringify(payload) } as MessageEvent
    for (const handler of handlers) {
      handler(event)
    }
  }
}

describe('useSSE', () => {
  beforeEach(() => {
    MockEventSource.instances = []
    vi.useRealTimers()
    vi.stubGlobal('EventSource', MockEventSource)
  })

  it('marks stream complete with cancelled state on cancelled event', async () => {
    const { result } = renderHook(() => useSSE('r1'))

    expect(MockEventSource.instances).toHaveLength(1)
    const es = MockEventSource.instances[0]

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

    expect(MockEventSource.instances).toHaveLength(1)
    const first = MockEventSource.instances[0]
    const duplicatedEvent = {
        type: 'source_completed',
        stage: 'github_search',
        message: 'Found 3 results from github',
        data: { platform: 'github', count: 3 },
        timestamp: '2026-02-24T14:00:00.000Z',
    }

    act(() => {
      first.emit('source_completed', duplicatedEvent)
      first.onerror?.()
    })

    await act(async () => {
      vi.runAllTimers()
      await Promise.resolve()
    })

    expect(MockEventSource.instances.length).toBeGreaterThanOrEqual(2)
    const second = MockEventSource.instances[1]
    act(() => {
      second.emit('source_completed', duplicatedEvent)
    })

    expect(result.current.events).toHaveLength(1)
  })
})
