import { useEffect, useReducer, useRef, useCallback } from 'react'
import type { PipelineEvent } from '../types/research'
import { getStreamUrl } from './client'

const MAX_RECONNECT_ATTEMPTS = 5
const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 15000

interface SSEState {
  events: PipelineEvent[]
  isComplete: boolean
  isReconnecting: boolean
  error: string | null
  cancelled: string | null
}

type SSEAction =
  | { type: 'reset' }
  | { type: 'event'; event: PipelineEvent }
  | { type: 'complete' }
  | { type: 'cancelled'; message: string }
  | { type: 'error'; message: string }
  | { type: 'reconnecting' }

function sseReducer(state: SSEState, action: SSEAction): SSEState {
  switch (action.type) {
    case 'reset':
      return { events: [], isComplete: false, isReconnecting: false, error: null, cancelled: null }
    case 'event':
      return { ...state, events: [...state.events, action.event], isReconnecting: false }
    case 'complete':
      return { ...state, isComplete: true, isReconnecting: false }
    case 'cancelled':
      return { ...state, cancelled: action.message, isComplete: true, isReconnecting: false }
    case 'error':
      return { ...state, error: action.message, cancelled: null, isComplete: true, isReconnecting: false }
    case 'reconnecting':
      return { ...state, isReconnecting: true }
  }
}

export interface UseSSEResult {
  events: PipelineEvent[]
  isComplete: boolean
  isReconnecting: boolean
  error: string | null
  cancelled: string | null
  retry: () => void
}

function createConnection(
  id: string,
  dispatch: React.Dispatch<SSEAction>,
  sourceRef: React.RefObject<EventSource | null>,
  attemptRef: React.RefObject<number>,
  reconnectTimerRef: React.RefObject<ReturnType<typeof setTimeout> | null>,
  isCompleteRef: React.RefObject<boolean>,
  selfRef: React.RefObject<((id: string) => void) | null>,
) {
  if (isCompleteRef.current) return

  if (sourceRef.current) {
    sourceRef.current.close()
    sourceRef.current = null
  }
  if (reconnectTimerRef.current) {
    clearTimeout(reconnectTimerRef.current)
    reconnectTimerRef.current = null
  }

  const es = new EventSource(getStreamUrl(id))
  sourceRef.current = es

  const handleEvent = (e: MessageEvent) => {
    try {
      const event: PipelineEvent = JSON.parse(e.data)
      attemptRef.current = 0
      dispatch({ type: 'event', event })
      if (event.type === 'report_ready') {
        dispatch({ type: 'complete' })
        es.close()
      }
      if (event.type === 'error') {
        dispatch({ type: 'error', message: event.message })
        es.close()
      }
      if (event.type === 'cancelled') {
        dispatch({ type: 'cancelled', message: event.message })
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
    'report_ready', 'cancelled', 'error',
  ]
  for (const t of eventTypes) {
    es.addEventListener(t, handleEvent)
  }

  es.onerror = () => {
    es.close()
    sourceRef.current = null

    if (isCompleteRef.current) return

    attemptRef.current = (attemptRef.current ?? 0) + 1
    if ((attemptRef.current ?? 0) > MAX_RECONNECT_ATTEMPTS) {
      dispatch({ type: 'error', message: 'Connection lost. Click retry to try again.' })
      return
    }

    dispatch({ type: 'reconnecting' })
    const delay = Math.min(BASE_DELAY_MS * Math.pow(2, (attemptRef.current ?? 1) - 1), MAX_DELAY_MS)
    reconnectTimerRef.current = setTimeout(() => selfRef.current?.(id), delay)
  }
}

export function useSSE(reportId: string | null): UseSSEResult {
  const [state, dispatch] = useReducer(sseReducer, {
    events: [],
    isComplete: false,
    isReconnecting: false,
    error: null,
    cancelled: null,
  })
  const sourceRef = useRef<EventSource | null>(null)
  const attemptRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isCompleteRef = useRef(false)
  const connectFnRef = useRef<((id: string) => void) | null>(null)

  useEffect(() => {
    isCompleteRef.current = state.isComplete
  }, [state.isComplete])

  useEffect(() => {
    connectFnRef.current = (id: string) =>
      createConnection(id, dispatch, sourceRef, attemptRef, reconnectTimerRef, isCompleteRef, connectFnRef)
  })

  const retry = useCallback(() => {
    if (!reportId) return
    dispatch({ type: 'reset' })
    attemptRef.current = 0
    connectFnRef.current?.(reportId)
  }, [reportId])

  useEffect(() => {
    if (!reportId) return

    dispatch({ type: 'reset' })
    attemptRef.current = 0
    const fn = (id: string) =>
      createConnection(id, dispatch, sourceRef, attemptRef, reconnectTimerRef, isCompleteRef, connectFnRef)
    connectFnRef.current = fn
    fn(reportId)

    return () => {
      if (sourceRef.current) {
        sourceRef.current.close()
        sourceRef.current = null
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
    }
  }, [reportId])

  return { ...state, retry }
}
