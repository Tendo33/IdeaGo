import { useState, useEffect } from 'react'
import { Check, Loader2, X, WifiOff, Clock } from 'lucide-react'
import type { PipelineEvent } from '../types/research'

interface Stage {
  id: string
  label: string
  status: 'pending' | 'active' | 'done' | 'failed'
  detail?: string
}

function deriveStages(events: PipelineEvent[]): Stage[] {
  const stages: Stage[] = [
    { id: 'intent', label: 'Analyzing your idea', status: 'pending' },
    { id: 'github', label: 'Searching GitHub', status: 'pending' },
    { id: 'tavily', label: 'Searching the web', status: 'pending' },
    { id: 'hackernews', label: 'Searching Hacker News', status: 'pending' },
    { id: 'extraction', label: 'Extracting competitor insights', status: 'pending' },
    { id: 'aggregation', label: 'Analyzing and deduplicating', status: 'pending' },
    { id: 'complete', label: 'Report ready', status: 'pending' },
  ]

  for (const event of events) {
    switch (event.type) {
      case 'intent_parsed':
        stages[0].status = 'done'
        stages[0].detail = event.message
        break
      case 'source_started':
        if (event.stage.includes('github')) stages[1].status = 'active'
        else if (event.stage.includes('tavily')) stages[2].status = 'active'
        else if (event.stage.includes('hackernews')) stages[3].status = 'active'
        break
      case 'source_completed': {
        const count = event.data?.count as number | undefined
        const msg = count !== undefined ? `Found ${count} results` : ''
        if (event.stage.includes('github')) { stages[1].status = 'done'; stages[1].detail = msg }
        else if (event.stage.includes('tavily')) { stages[2].status = 'done'; stages[2].detail = msg }
        else if (event.stage.includes('hackernews')) { stages[3].status = 'done'; stages[3].detail = msg }
        break
      }
      case 'source_failed':
        if (event.stage.includes('github')) { stages[1].status = 'failed'; stages[1].detail = event.message }
        else if (event.stage.includes('tavily')) { stages[2].status = 'failed'; stages[2].detail = event.message }
        else if (event.stage.includes('hackernews')) { stages[3].status = 'failed'; stages[3].detail = event.message }
        break
      case 'extraction_started':
        stages[4].status = 'active'
        break
      case 'extraction_completed':
        stages[4].status = 'done'
        stages[4].detail = event.message
        break
      case 'aggregation_started':
        stages[5].status = 'active'
        break
      case 'aggregation_completed':
        stages[5].status = 'done'
        stages[5].detail = event.message
        break
      case 'report_ready':
        stages[6].status = 'done'
        break
      case 'error':
        stages[6].status = 'failed'
        stages[6].detail = event.message
        break
    }
  }

  return stages
}

function StageIcon({ status }: { status: Stage['status'] }) {
  switch (status) {
    case 'done':
      return <div className="w-8 h-8 rounded-full bg-cta/20 flex items-center justify-center"><Check className="w-4 h-4 text-cta" /></div>
    case 'active':
      return <div className="w-8 h-8 rounded-full bg-cta/10 flex items-center justify-center"><Loader2 className="w-4 h-4 text-cta animate-spin" /></div>
    case 'failed':
      return <div className="w-8 h-8 rounded-full bg-danger/20 flex items-center justify-center"><X className="w-4 h-4 text-danger" /></div>
    default:
      return <div className="w-8 h-8 rounded-full bg-border flex items-center justify-center"><div className="w-2 h-2 rounded-full bg-text-dim" /></div>
  }
}

interface ProgressTrackerProps {
  events: PipelineEvent[]
  isReconnecting?: boolean
}

function useElapsed() {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => clearInterval(t)
  }, [])
  return elapsed
}

export function ProgressTracker({ events, isReconnecting = false }: ProgressTrackerProps) {
  const stages = deriveStages(events)
  const elapsed = useElapsed()
  const isDone = stages.at(-1)?.status === 'done' || stages.at(-1)?.status === 'failed'

  return (
    <div className="w-full max-w-lg mx-auto py-8">
      {!isDone && (
        <div className="flex items-center justify-between mb-5 px-1">
          <p className="text-xs text-text-dim flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            Elapsed: {elapsed}s
          </p>
          <p className="text-xs text-text-dim">Usually takes 20–30 seconds</p>
        </div>
      )}
      {isReconnecting && (
        <div className="flex items-center gap-2 px-3 py-2 mb-4 rounded-lg bg-warning/10 border border-warning/30 text-xs text-warning">
          <WifiOff className="w-3.5 h-3.5 shrink-0" />
          Reconnecting to server...
        </div>
      )}
      <div className="space-y-1">
        {stages.map((stage, i) => (
          <div key={stage.id} className="flex items-start gap-4">
            <div className="flex flex-col items-center">
              <StageIcon status={stage.status} />
              {i < stages.length - 1 && (
                <div className={`w-0.5 h-8 mt-1 transition-colors duration-300 ${stage.status === 'done' ? 'bg-cta/40' : 'bg-border'}`} />
              )}
            </div>
            <div className="pt-1 min-w-0">
              <p className={`text-sm font-medium transition-colors duration-200 ${stage.status === 'active' ? 'text-cta' : stage.status === 'done' ? 'text-text' : stage.status === 'failed' ? 'text-danger' : 'text-text-dim'}`}>
                {stage.label}
              </p>
              {stage.detail && (
                <p className="text-xs text-text-muted mt-0.5 truncate">{stage.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
