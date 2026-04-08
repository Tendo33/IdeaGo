import type { PipelineEvent } from '../types/research'

const MAX_EVENT_HISTORY = 200
const RETRYABLE_HTTP_STATUS = new Set([408, 409, 425, 429, 500, 502, 503, 504])

export interface SSEState {
  events: PipelineEvent[]
  pendingEvents: PipelineEvent[]
  isComplete: boolean
  isReconnecting: boolean
  error: string | null
  cancelled: string | null
  pendingTerminalState: { type: 'complete' | 'cancelled' | 'error'; message?: string } | null
}

export type SSEAction =
  | { type: 'reset' }
  | { type: 'event'; event: PipelineEvent }
  | { type: 'flush' }
  | { type: 'connected' }
  | { type: 'complete' }
  | { type: 'cancelled'; message: string }
  | { type: 'error'; message: string }
  | { type: 'reconnecting' }

export const initialSSEState: SSEState = {
  events: [],
  pendingEvents: [],
  isComplete: false,
  isReconnecting: false,
  error: null,
  cancelled: null,
  pendingTerminalState: null,
}

function eventKey(event: PipelineEvent): string {
  return `${event.type}|${event.stage}|${event.timestamp}`
}

export function sseReducer(state: SSEState, action: SSEAction): SSEState {
  switch (action.type) {
    case 'reset':
      return initialSSEState
    case 'event':
      if (
        state.events.some((existing) => eventKey(existing) === eventKey(action.event)) ||
        state.pendingEvents.some((existing) => eventKey(existing) === eventKey(action.event))
      ) {
        return { ...state, isReconnecting: false }
      }
      return {
        ...state,
        pendingEvents: [...state.pendingEvents, action.event],
        isReconnecting: false,
      }
    case 'flush': {
      if (state.pendingEvents.length === 0) {
        if (state.pendingTerminalState) {
          if (state.pendingTerminalState.type === 'complete') {
            return {
              ...state,
              isComplete: true,
              isReconnecting: false,
              pendingTerminalState: null,
            }
          }
          if (state.pendingTerminalState.type === 'error') {
            return {
              ...state,
              error: state.pendingTerminalState.message ?? null,
              isComplete: true,
              isReconnecting: false,
              pendingTerminalState: null,
            }
          }
          return {
            ...state,
            cancelled: state.pendingTerminalState.message ?? null,
            isComplete: true,
            isReconnecting: false,
            pendingTerminalState: null,
          }
        }
        return state
      }

      return {
        ...state,
        events: [...state.events, state.pendingEvents[0]].slice(-MAX_EVENT_HISTORY),
        pendingEvents: state.pendingEvents.slice(1),
      }
    }
    case 'connected':
      return { ...state, isReconnecting: false }
    case 'complete':
      if (state.pendingEvents.length > 0) {
        return { ...state, pendingTerminalState: { type: 'complete' } }
      }
      return { ...state, isComplete: true, isReconnecting: false }
    case 'cancelled':
      if (state.pendingEvents.length > 0) {
        return {
          ...state,
          pendingTerminalState: { type: 'cancelled', message: action.message },
        }
      }
      return { ...state, cancelled: action.message, isComplete: true, isReconnecting: false }
    case 'error':
      if (state.pendingEvents.length > 0) {
        return {
          ...state,
          pendingTerminalState: { type: 'error', message: action.message },
        }
      }
      return {
        ...state,
        error: action.message,
        cancelled: null,
        isComplete: true,
        isReconnecting: false,
      }
    case 'reconnecting':
      return { ...state, isReconnecting: true }
  }
}

export function clearReconnectTimer(timerRef: {
  current: ReturnType<typeof setTimeout> | null
}): void {
  if (timerRef.current) {
    clearTimeout(timerRef.current)
    timerRef.current = null
  }
}

export function findLastSseBoundary(buffer: string): number {
  const boundaryPattern = /\r?\n\r?\n/g
  let boundaryEnd = -1
  let match: RegExpExecArray | null
  while ((match = boundaryPattern.exec(buffer)) !== null) {
    boundaryEnd = match.index + match[0].length
  }
  return boundaryEnd
}

export function shouldRetrySseStatus(statusCode: number): boolean {
  if (statusCode >= 200 && statusCode < 300) {
    return false
  }
  if (statusCode >= 400 && statusCode < 500) {
    return RETRYABLE_HTTP_STATUS.has(statusCode)
  }
  return true
}

export function* parseSseChunk(
  buffer: string,
): Generator<{ eventType: string; data: string }> {
  const blocks = buffer.split(/\r?\n\r?\n/)
  for (const block of blocks) {
    if (!block.trim()) continue
    let eventType = 'message'
    const dataLines: string[] = []
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trimStart())
      }
    }
    const data = dataLines.join('\n')
    if (data) yield { eventType, data }
  }
}
