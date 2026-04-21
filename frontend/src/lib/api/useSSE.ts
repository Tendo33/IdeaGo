import { useCallback, useEffect, useReducer, useRef } from 'react'
import i18n from '@/lib/i18n/i18n'
import { parsePipelineEvent, type PipelineEvent } from '@/lib/types/research'
import { getStreamUrl } from '@/lib/api/client'
import { readCurrentReturnTo } from '@/lib/auth/redirect'
import { getAccessToken, setAccessToken } from '@/lib/auth/token'
import { supabase } from '@/lib/supabase/client'
import { clearHistoryCache } from '@/features/history/historyCache'
import { findLastSseBoundary, parseSseChunk, shouldRetrySseStatus } from '@/lib/api/sse/parser'
import { sseReducer } from '@/lib/api/sse/reducer'
import { recordClientMetric } from '@/lib/telemetry/clientMetrics'

const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 15000
const MAX_RECONNECT_ATTEMPTS = 5
const STREAM_EVENT_TYPES = new Set([
  'intent_started',
  'intent_parsed',
  'query_planning_started',
  'query_planning_completed',
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
])

export interface UseSSEResult {
  events: PipelineEvent[]
  isComplete: boolean
  isReconnecting: boolean
  error: string | null
  cancelled: string | null
  reconnectAttempts?: number
  lastFailureReason?: string | null
  retry: () => void
}

function clearReconnectTimer(timerRef: React.RefObject<ReturnType<typeof setTimeout> | null>): void {
  if (timerRef.current) {
    clearTimeout(timerRef.current)
    timerRef.current = null
  }
}

function redirectToLogin(): void {
  setAccessToken(null)
  clearHistoryCache()
  supabase.auth.signOut().catch(() => {})
  const returnTo = encodeURIComponent(readCurrentReturnTo())
  window.location.href = `/login?returnTo=${returnTo}`
}

export function useSSE(reportId: string | null): UseSSEResult {
  const [state, dispatch] = useReducer(sseReducer, {
    events: [],
    pendingEvents: [],
    isComplete: false,
    isReconnecting: false,
    error: null,
    cancelled: null,
    pendingTerminalState: null,
  })
  const abortRef = useRef<AbortController | null>(null)
  const attemptRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const lastFailureReasonRef = useRef<string | null>(null)
  const isCompleteRef = useRef(false)
  const connectRef = useRef<((id: string) => void) | null>(null)

  useEffect(() => {
    if (state.pendingEvents.length > 0 || state.pendingTerminalState) {
      const timer = setTimeout(() => dispatch({ type: 'flush' }), 300)
      return () => clearTimeout(timer)
    }
  }, [state.pendingEvents.length, state.pendingTerminalState])

  useEffect(() => {
    isCompleteRef.current = state.isComplete
  }, [state.isComplete])

  const cleanupConnection = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
  }, [])

  const connect = useCallback((id: string) => {
    if (isCompleteRef.current) return
    cleanupConnection()
    clearReconnectTimer(reconnectTimerRef)

    const controller = new AbortController()
    abortRef.current = controller

    const url = getStreamUrl(id)

    ;(async () => {
      let hasConfirmedConnection = false

      const confirmConnection = () => {
        attemptRef.current = 0
        if (!hasConfirmedConnection) {
          hasConfirmedConnection = true
          reconnectAttemptsRef.current = 0
          lastFailureReasonRef.current = null
        }
        dispatch({ type: 'connected' })
      }

      try {
        const headers: Record<string, string> = { Accept: 'text/event-stream' }
        const token = getAccessToken()
        if (token) headers.Authorization = `Bearer ${token}`

        const response = await fetch(url, {
          headers,
          signal: controller.signal,
          credentials: 'include',
        })

        if (!response.ok || !response.body) {
          if (response.status === 401) {
            redirectToLogin()
            return
          }
          if (!response.ok && !shouldRetrySseStatus(response.status)) {
            dispatch({ type: 'error', message: i18n.t('report.error.connectionLost') })
            return
          }
          throw new Error(`SSE connection failed: ${response.status}`)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lastBoundary = findLastSseBoundary(buffer)
          if (lastBoundary === -1) continue

          const toProcess = buffer.slice(0, lastBoundary)
          buffer = buffer.slice(lastBoundary)

          for (const { eventType, data } of parseSseChunk(toProcess)) {
            if (eventType === 'ping') {
              confirmConnection()
              continue
            }
            if (!STREAM_EVENT_TYPES.has(eventType)) continue

            try {
              const parsed = parsePipelineEvent(JSON.parse(data), eventType as PipelineEvent['type'])
              if (!parsed) continue
              const event: PipelineEvent = parsed
              confirmConnection()
              dispatch({ type: 'event', event })

              if (event.type === 'report_ready') {
                dispatch({ type: 'complete' })
                return
              }
              if (event.type === 'error') {
                dispatch({ type: 'error', message: event.message })
                return
              }
              if (event.type === 'cancelled') {
                dispatch({ type: 'cancelled', message: event.message })
                return
              }
            } catch {
              // Ignore malformed payloads while keeping stream alive.
            }
          }
        }

        if (!isCompleteRef.current) {
          throw new Error('Stream closed unexpectedly')
        }
      } catch (error) {
        if ((error as Error).name === 'AbortError') return
        if (isCompleteRef.current) return

        attemptRef.current += 1
        reconnectAttemptsRef.current += 1
        lastFailureReasonRef.current = error instanceof Error ? error.message : 'unknown'
        if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          recordClientMetric('sse_reconnect_exhausted', {
            reportId: id,
            attempts: reconnectAttemptsRef.current,
            reason: lastFailureReasonRef.current ?? 'unknown',
          })
          dispatch({ type: 'error', message: i18n.t('report.error.connectionLost') })
          return
        }
        dispatch({ type: 'reconnecting' })
        const delay = Math.min(
          BASE_DELAY_MS * Math.pow(2, attemptRef.current - 1),
          MAX_DELAY_MS,
        )
        reconnectTimerRef.current = setTimeout(() => connectRef.current?.(id), delay)
      }
    })()
  }, [cleanupConnection])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  const retry = useCallback(() => {
    if (!reportId) return
    dispatch({ type: 'reset' })
    attemptRef.current = 0
    reconnectAttemptsRef.current = 0
    lastFailureReasonRef.current = null
    isCompleteRef.current = false
    connect(reportId)
  }, [connect, reportId])

  useEffect(() => {
    if (!reportId) return
    dispatch({ type: 'reset' })
    attemptRef.current = 0
    reconnectAttemptsRef.current = 0
    lastFailureReasonRef.current = null
    isCompleteRef.current = false
    connect(reportId)

    return () => {
      cleanupConnection()
      clearReconnectTimer(reconnectTimerRef)
    }
  }, [cleanupConnection, connect, reportId])

  return {
    events: state.events,
    isComplete: state.isComplete,
    isReconnecting: state.isReconnecting,
    error: state.error,
    cancelled: state.cancelled,
    reconnectAttempts: reconnectAttemptsRef.current,
    lastFailureReason: lastFailureReasonRef.current,
    retry,
  }
}
