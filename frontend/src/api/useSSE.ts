import { useEffect, useReducer, useRef } from 'react'
import type { PipelineEvent } from '../types/research'
import { getStreamUrl } from './client'

interface SSEState {
  events: PipelineEvent[]
  isComplete: boolean
  error: string | null
}

type SSEAction =
  | { type: 'reset' }
  | { type: 'event'; event: PipelineEvent }
  | { type: 'complete' }
  | { type: 'error'; message: string }

function sseReducer(state: SSEState, action: SSEAction): SSEState {
  switch (action.type) {
    case 'reset':
      return { events: [], isComplete: false, error: null }
    case 'event':
      return { ...state, events: [...state.events, action.event] }
    case 'complete':
      return { ...state, isComplete: true }
    case 'error':
      return { ...state, error: action.message, isComplete: true }
  }
}

export interface UseSSEResult {
  events: PipelineEvent[]
  isComplete: boolean
  error: string | null
}

export function useSSE(reportId: string | null): UseSSEResult {
  const [state, dispatch] = useReducer(sseReducer, {
    events: [],
    isComplete: false,
    error: null,
  })
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!reportId) return

    dispatch({ type: 'reset' })

    if (sourceRef.current) {
      sourceRef.current.close()
    }

    const es = new EventSource(getStreamUrl(reportId))
    sourceRef.current = es

    const handleEvent = (e: MessageEvent) => {
      try {
        const event: PipelineEvent = JSON.parse(e.data)
        dispatch({ type: 'event', event })
        if (event.type === 'report_ready') {
          dispatch({ type: 'complete' })
          es.close()
        }
        if (event.type === 'error') {
          dispatch({ type: 'error', message: event.message })
          es.close()
        }
      } catch {
        // ignore parse errors from ping events
      }
    }

    const eventTypes = [
      'intent_parsed', 'source_started', 'source_completed', 'source_failed',
      'extraction_started', 'extraction_completed',
      'aggregation_started', 'aggregation_completed',
      'report_ready', 'error',
    ]
    for (const t of eventTypes) {
      es.addEventListener(t, handleEvent)
    }
    es.onerror = () => {
      dispatch({ type: 'error', message: 'Connection lost' })
      es.close()
    }

    return () => {
      es.close()
      sourceRef.current = null
    }
  }, [reportId])

  return state
}
