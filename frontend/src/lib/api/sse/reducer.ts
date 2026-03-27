import type { PipelineEvent } from '@/lib/types/research'

const MAX_EVENT_HISTORY = 200

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
      const nextEvent = state.pendingEvents[0]
      return {
        ...state,
        events: [...state.events, nextEvent].slice(-MAX_EVENT_HISTORY),
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
