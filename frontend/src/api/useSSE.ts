import { useCallback, useEffect, useRef, useState } from 'react'
import type { PipelineEvent } from '../types/research'
import { getStreamUrl } from './client'

interface UseSSEResult {
  events: PipelineEvent[]
  isComplete: boolean
  error: string | null
}

export function useSSE(reportId: string | null): UseSSEResult {
  const [events, setEvents] = useState<PipelineEvent[]>([])
  const [isComplete, setIsComplete] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const sourceRef = useRef<EventSource | null>(null)

  const cleanup = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close()
      sourceRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!reportId) return
    cleanup()
    setEvents([])
    setIsComplete(false)
    setError(null)

    const es = new EventSource(getStreamUrl(reportId))
    sourceRef.current = es

    const handleEvent = (e: MessageEvent) => {
      try {
        const event: PipelineEvent = JSON.parse(e.data)
        setEvents(prev => [...prev, event])
        if (event.type === 'report_ready') {
          setIsComplete(true)
          es.close()
        }
        if (event.type === 'error') {
          setError(event.message)
          setIsComplete(true)
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
      setError('Connection lost')
      setIsComplete(true)
      es.close()
    }

    return cleanup
  }, [reportId, cleanup])

  return { events, isComplete, error }
}
