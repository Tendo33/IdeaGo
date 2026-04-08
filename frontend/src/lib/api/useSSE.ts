import { useCallback, useEffect, useReducer, useRef } from 'react'
import i18n from '../i18n/i18n'
import { parsePipelineEvent, type PipelineEvent } from '../types/research'
import {
  getClientSessionId,
  getReportRuntimeStatus,
  getStreamUrl,
  isApiError,
  isRequestAbortError,
} from './client'
import {
  clearReconnectTimer,
  findLastSseBoundary,
  initialSSEState,
  parseSseChunk,
  shouldRetrySseStatus,
  sseReducer,
} from './sseState'

const BASE_DELAY_MS = 1000
const MAX_DELAY_MS = 15000
const MAX_RECONNECT_ATTEMPTS = 4
const STATUS_FALLBACK_POLL_MS = 3000
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
  retry: () => void
}

export function useSSE(reportId: string | null): UseSSEResult {
  const [state, dispatch] = useReducer(sseReducer, initialSSEState)
  const abortRef = useRef<AbortController | null>(null)
  const statusAbortRef = useRef<AbortController | null>(null)
  const attemptRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isCompleteRef = useRef(false)
  const connectRef = useRef<((id: string) => void) | null>(null)

  useEffect(() => {
    if (state.pendingEvents.length > 0 || state.pendingTerminalState) {
      const timer = setTimeout(() => {
        dispatch({ type: 'flush' })
      }, 300)
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

  const cleanupStatusPolling = useCallback(() => {
    if (statusAbortRef.current) {
      statusAbortRef.current.abort()
      statusAbortRef.current = null
    }
  }, [])

  const pollRuntimeStatus = useCallback(async (id: string) => {
    cleanupStatusPolling()
    const controller = new AbortController()
    statusAbortRef.current = controller

    try {
      const status = await getReportRuntimeStatus(id, { signal: controller.signal })
      if (controller.signal.aborted) {
        return
      }
      statusAbortRef.current = null

      if (status.status === 'complete') {
        dispatch({ type: 'complete' })
        return
      }
      if (status.status === 'cancelled') {
        dispatch({
          type: 'cancelled',
          message: status.message ?? i18n.t('report.error.cancelledStatus'),
        })
        return
      }
      if (status.status === 'failed' || status.status === 'not_found') {
        dispatch({
          type: 'error',
          message: status.message ?? i18n.t('report.error.connectionLost'),
        })
        return
      }

      reconnectTimerRef.current = setTimeout(() => {
        void pollRuntimeStatus(id)
      }, STATUS_FALLBACK_POLL_MS)
    } catch (error) {
      if (controller.signal.aborted || isRequestAbortError(error)) {
        return
      }
      statusAbortRef.current = null
      dispatch({
        type: 'error',
        message: isApiError(error)
          ? error.message
          : error instanceof Error && error.message.trim().length > 0
            ? error.message
            : i18n.t('report.error.connectionLost'),
      })
    }
  }, [cleanupStatusPolling])

  const connect = useCallback(
    (id: string) => {
      if (isCompleteRef.current) return
      cleanupConnection()
      cleanupStatusPolling()
      clearReconnectTimer(reconnectTimerRef)

      const controller = new AbortController()
      abortRef.current = controller

      const url = getStreamUrl(id)

      void (async () => {
        try {
          const res = await fetch(url, {
            headers: {
              Accept: 'text/event-stream',
              'X-Session-Id': getClientSessionId(),
            },
            signal: controller.signal,
          })

          if (!res.ok || !res.body) {
            if (!res.ok && !shouldRetrySseStatus(res.status)) {
              dispatch({
                type: 'error',
                message: i18n.t('report.error.connectionLost'),
              })
              return
            }
            throw new Error(`SSE connection failed: ${res.status}`)
          }
          attemptRef.current = 0
          dispatch({ type: 'connected' })

          const reader = res.body.getReader()
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
                attemptRef.current = 0
                dispatch({ type: 'connected' })
                continue
              }
              if (!STREAM_EVENT_TYPES.has(eventType)) continue

              try {
                const parsed = parsePipelineEvent(
                  JSON.parse(data),
                  eventType as PipelineEvent['type'],
                )
                if (!parsed) continue

                const event: PipelineEvent = parsed
                attemptRef.current = 0
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
                // Ignore malformed event payloads and keep the stream alive.
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
          dispatch({ type: 'reconnecting' })
          if (attemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
            clearReconnectTimer(reconnectTimerRef)
            void pollRuntimeStatus(id)
            return
          }
          const delay = Math.min(
            BASE_DELAY_MS * Math.pow(2, attemptRef.current - 1),
            MAX_DELAY_MS,
          )
          reconnectTimerRef.current = setTimeout(() => connectRef.current?.(id), delay)
        }
      })()
    },
    [cleanupConnection, cleanupStatusPolling, pollRuntimeStatus],
  )

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  const retry = useCallback(() => {
    if (!reportId) return
    dispatch({ type: 'reset' })
    attemptRef.current = 0
    isCompleteRef.current = false
    cleanupStatusPolling()
    clearReconnectTimer(reconnectTimerRef)
    connect(reportId)
  }, [cleanupStatusPolling, connect, reportId])

  useEffect(() => {
    if (!reportId) return

    dispatch({ type: 'reset' })
    attemptRef.current = 0
    isCompleteRef.current = false
    connect(reportId)

    return () => {
      cleanupConnection()
      cleanupStatusPolling()
      clearReconnectTimer(reconnectTimerRef)
    }
  }, [cleanupConnection, cleanupStatusPolling, connect, reportId])

  return {
    events: state.events,
    isComplete: state.isComplete,
    isReconnecting: state.isReconnecting,
    error: state.error,
    cancelled: state.cancelled,
    retry,
  }
}
