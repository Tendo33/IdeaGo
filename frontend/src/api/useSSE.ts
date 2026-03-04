import { useEffect, useReducer, useRef, useCallback } from 'react'
import i18n from '../i18n'
import type { PipelineEvent } from '../types/research'
import { getStreamUrl } from './client'

const MAX_RECONNECT_ATTEMPTS = 5
const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 15000
const MAX_EVENT_HISTORY = 200
const STREAM_EVENT_TYPES = [
  'intent_started',
  'intent_parsed',
  'source_started',
  'source_completed',
  'source_failed',
  'extraction_started',
  'extraction_completed',
  'aggregation_started',
  'aggregation_completed',
  'report_ready',
  'cancelled',
  'error',
] as const

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

function eventKey(event: PipelineEvent): string {
  return `${event.type}|${event.stage}|${event.timestamp}`
}

function sseReducer(state: SSEState, action: SSEAction): SSEState {
  switch (action.type) {
    case 'reset':
      return { events: [], isComplete: false, isReconnecting: false, error: null, cancelled: null }
    case 'event':
      if (state.events.some(existing => eventKey(existing) === eventKey(action.event))) {
        return { ...state, isReconnecting: false }
      }
      return {
        ...state,
        events: [...state.events, action.event].slice(-MAX_EVENT_HISTORY),
        isReconnecting: false,
      }
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

function clearReconnectTimer(timerRef: React.RefObject<ReturnType<typeof setTimeout> | null>): void {
  if (timerRef.current) {
    clearTimeout(timerRef.current)
    timerRef.current = null
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
  const cleanupConnectionRef = useRef<(() => void) | null>(null)
  const connectRef = useRef<((id: string) => void) | null>(null)

  const cleanupConnection = useCallback(() => {
    if (cleanupConnectionRef.current) {
      cleanupConnectionRef.current()
      cleanupConnectionRef.current = null
      return
    }
    if (sourceRef.current) {
      sourceRef.current.close()
      sourceRef.current = null
    }
  }, [])

  useEffect(() => {
    isCompleteRef.current = state.isComplete
  }, [state.isComplete])

  const connect = useCallback((id: string) => {
    if (isCompleteRef.current) return
    cleanupConnection()
    clearReconnectTimer(reconnectTimerRef)

    const es = new EventSource(getStreamUrl(id))
    sourceRef.current = es

    const cleanupCurrentEventSource = () => {
      for (const eventType of STREAM_EVENT_TYPES) {
        es.removeEventListener(eventType, handleEvent)
      }
      es.onerror = null
      es.close()
      if (sourceRef.current === es) {
        sourceRef.current = null
      }
    }

    const handleEvent = (e: MessageEvent) => {
      if (sourceRef.current !== es) return
      try {
        const event: PipelineEvent = JSON.parse(e.data)
        attemptRef.current = 0
        dispatch({ type: 'event', event })
        if (event.type === 'report_ready') {
          dispatch({ type: 'complete' })
          cleanupCurrentEventSource()
          cleanupConnectionRef.current = null
        }
        if (event.type === 'error') {
          dispatch({ type: 'error', message: event.message })
          cleanupCurrentEventSource()
          cleanupConnectionRef.current = null
        }
        if (event.type === 'cancelled') {
          dispatch({ type: 'cancelled', message: event.message })
          cleanupCurrentEventSource()
          cleanupConnectionRef.current = null
        }
      } catch {
        // ignore parse errors from ping events
      }
    }

    cleanupConnectionRef.current = cleanupCurrentEventSource
    for (const eventType of STREAM_EVENT_TYPES) {
      es.addEventListener(eventType, handleEvent)
    }

    es.onerror = () => {
      if (sourceRef.current !== es) return
      cleanupCurrentEventSource()
      cleanupConnectionRef.current = null

      if (isCompleteRef.current) return

      attemptRef.current += 1
      if (attemptRef.current > MAX_RECONNECT_ATTEMPTS) {
        dispatch({ type: 'error', message: i18n.t('report.error.connectionLost') })
        return
      }

      dispatch({ type: 'reconnecting' })
      const delay = Math.min(BASE_DELAY_MS * Math.pow(2, attemptRef.current - 1), MAX_DELAY_MS)
      reconnectTimerRef.current = setTimeout(() => connectRef.current?.(id), delay)
    }
  }, [cleanupConnection])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  const retry = useCallback(() => {
    if (!reportId) return
    dispatch({ type: 'reset' })
    attemptRef.current = 0
    isCompleteRef.current = false
    connect(reportId)
  }, [connect, reportId])

  useEffect(() => {
    if (!reportId) return

    dispatch({ type: 'reset' })
    attemptRef.current = 0
    isCompleteRef.current = false
    connect(reportId)

    return () => {
      cleanupConnection()
      clearReconnectTimer(reconnectTimerRef)
    }
  }, [cleanupConnection, connect, reportId])

  return { ...state, retry }
}
