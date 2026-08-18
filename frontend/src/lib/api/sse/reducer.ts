import type { PipelineEvent } from '@/lib/types/research'

const MAX_EVENT_HISTORY = 200
// A backlog drains in a few ticks instead of one-per-tick: with a divisor of 4,
// 40 queued events clear in ~5 ticks rather than 40.
const FLUSH_BATCH_DIVISOR = 4

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

function eventKey(event: PipelineEvent): string {
  return `${event.type}|${event.stage}|${event.timestamp}`
}

export function sseReducer(state: SSEState, action: SSEAction): SSEState {
  switch (action.type) {
    case 'reset':
      return { events: [], pendingEvents: [], isComplete: false, isReconnecting: false, error: null, cancelled: null, pendingTerminalState: null }
    case 'event':
      if (state.events.some(existing => eventKey(existing) === eventKey(action.event)) ||
          state.pendingEvents.some(existing => eventKey(existing) === eventKey(action.event))) {
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
            return { ...state, isComplete: true, isReconnecting: false, pendingTerminalState: null }
          } else if (state.pendingTerminalState.type === 'error') {
            return { ...state, error: state.pendingTerminalState.message ?? null, isComplete: true, isReconnecting: false, pendingTerminalState: null }
          } else if (state.pendingTerminalState.type === 'cancelled') {
            return { ...state, cancelled: state.pendingTerminalState.message ?? null, isComplete: true, isReconnecting: false, pendingTerminalState: null }
          }
        }
        return state
      }
      // Drain in batches rather than one event per tick.
      //
      // The staggered reveal reads well while events trickle in live, but the
      // backend replays the full history on reconnect (and when opening an
      // in-progress report). At one event per 300ms a 40-event replay took
      // ~12 seconds to catch up, during which the progress pane looked frozen
      // and behind reality. Draining a batch keeps the pacing for live runs
      // while letting a backlog catch up quickly.
      const batchSize = Math.max(1, Math.ceil(state.pendingEvents.length / FLUSH_BATCH_DIVISOR))
      const batch = state.pendingEvents.slice(0, batchSize)
      return {
        ...state,
        events: [...state.events, ...batch].slice(-MAX_EVENT_HISTORY),
        pendingEvents: state.pendingEvents.slice(batchSize),
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
        return { ...state, pendingTerminalState: { type: 'cancelled', message: action.message } }
      }
      return { ...state, cancelled: action.message, isComplete: true, isReconnecting: false }
    case 'error':
      if (state.pendingEvents.length > 0) {
        return { ...state, pendingTerminalState: { type: 'error', message: action.message } }
      }
      return { ...state, error: action.message, cancelled: null, isComplete: true, isReconnecting: false }
    case 'reconnecting':
      return { ...state, isReconnecting: true }
  }
}
