import { Check, X, Loader2, WifiOff, Clock } from 'lucide-react'
import { useState, useEffect } from 'react'
import type { PipelineEvent } from '../types/research'

interface Step {
  id: string
  label: string
  shortLabel: string
  status: 'pending' | 'active' | 'done' | 'failed'
  detail?: string
}

function deriveSteps(events: PipelineEvent[]): Step[] {
  const steps: Step[] = [
    { id: 'intent', label: 'Analyzing idea', shortLabel: 'Idea', status: 'pending' },
    { id: 'github', label: 'Searching GitHub', shortLabel: 'GitHub', status: 'pending' },
    { id: 'tavily', label: 'Searching web', shortLabel: 'Web', status: 'pending' },
    { id: 'hackernews', label: 'Searching HN', shortLabel: 'HN', status: 'pending' },
    { id: 'extraction', label: 'Extracting insights', shortLabel: 'Extract', status: 'pending' },
    { id: 'aggregation', label: 'Analyzing data', shortLabel: 'Analyze', status: 'pending' },
    { id: 'complete', label: 'Report ready', shortLabel: 'Done', status: 'pending' },
  ]

  for (const event of events) {
    switch (event.type) {
      case 'intent_parsed':
        steps[0].status = 'done'
        break
      case 'source_started':
        if (event.stage.includes('github')) steps[1].status = 'active'
        else if (event.stage.includes('tavily')) steps[2].status = 'active'
        else if (event.stage.includes('hackernews')) steps[3].status = 'active'
        break
      case 'source_completed': {
        const count = event.data?.count as number | undefined
        if (event.stage.includes('github')) { steps[1].status = 'done'; steps[1].detail = count !== undefined ? `${count}` : undefined }
        else if (event.stage.includes('tavily')) { steps[2].status = 'done'; steps[2].detail = count !== undefined ? `${count}` : undefined }
        else if (event.stage.includes('hackernews')) { steps[3].status = 'done'; steps[3].detail = count !== undefined ? `${count}` : undefined }
        break
      }
      case 'source_failed':
        if (event.stage.includes('github')) steps[1].status = 'failed'
        else if (event.stage.includes('tavily')) steps[2].status = 'failed'
        else if (event.stage.includes('hackernews')) steps[3].status = 'failed'
        break
      case 'extraction_started':
        steps[4].status = 'active'
        break
      case 'extraction_completed':
        steps[4].status = 'done'
        break
      case 'aggregation_started':
        steps[5].status = 'active'
        break
      case 'aggregation_completed':
        steps[5].status = 'done'
        break
      case 'report_ready':
        steps[6].status = 'done'
        break
      case 'error':
        steps[6].status = 'failed'
        break
    }
  }

  return steps
}

function StepDot({ status, detail }: { status: Step['status']; detail?: string }) {
  const base = 'w-7 h-7 rounded-full flex items-center justify-center shrink-0 transition-all duration-300'

  switch (status) {
    case 'done':
      return (
        <div className={`${base} bg-cta/20`}>
          {detail ? (
            <span className="text-[9px] font-bold text-cta">{detail}</span>
          ) : (
            <Check className="w-3.5 h-3.5 text-cta" />
          )}
        </div>
      )
    case 'active':
      return (
        <div className={`${base} bg-cta/10 animate-verdict-pulse`}>
          <Loader2 className="w-3.5 h-3.5 text-cta animate-spin" />
        </div>
      )
    case 'failed':
      return (
        <div className={`${base} bg-danger/20`}>
          <X className="w-3.5 h-3.5 text-danger" />
        </div>
      )
    default:
      return (
        <div className={`${base} bg-border`}>
          <div className="w-1.5 h-1.5 rounded-full bg-text-dim" />
        </div>
      )
  }
}

function Connector({ done }: { done: boolean }) {
  return (
    <div className={`flex-1 h-0.5 mx-0.5 rounded-full transition-colors duration-500 ${done ? 'bg-cta/40' : 'bg-border'}`} />
  )
}

function useElapsed() {
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => clearInterval(t)
  }, [])
  return elapsed
}

interface HorizontalStepperProps {
  events: PipelineEvent[]
  isReconnecting?: boolean
}

export function HorizontalStepper({ events, isReconnecting = false }: HorizontalStepperProps) {
  const steps = deriveSteps(events)
  const elapsed = useElapsed()
  const isDone = steps.at(-1)?.status === 'done' || steps.at(-1)?.status === 'failed'

  return (
    <div className="w-full py-6">
      {isReconnecting && (
        <div className="flex items-center gap-2 px-3 py-2 mb-4 rounded-lg bg-warning/10 border border-warning/30 text-xs text-warning mx-auto max-w-md">
          <WifiOff className="w-3.5 h-3.5 shrink-0" />
          Reconnecting to server...
        </div>
      )}

      {/* Stepper Row */}
      <div className="flex items-center w-full max-w-3xl mx-auto px-2">
        {steps.map((step, i) => (
          <div key={step.id} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1.5 min-w-0">
              <StepDot status={step.status} detail={step.detail} />
              <span className={`text-[10px] text-center leading-tight truncate max-w-[60px] transition-colors duration-200 ${
                step.status === 'active' ? 'text-cta font-medium' :
                step.status === 'done' ? 'text-text' :
                step.status === 'failed' ? 'text-danger' :
                'text-text-dim'
              }`}>
                {step.shortLabel}
              </span>
            </div>
            {i < steps.length - 1 && (
              <Connector done={step.status === 'done'} />
            )}
          </div>
        ))}
      </div>

      {/* Elapsed time */}
      {!isDone && (
        <div className="flex items-center justify-center gap-4 mt-4 text-xs text-text-dim">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {elapsed}s elapsed
          </span>
          <span>Usually 20–30 seconds</span>
        </div>
      )}
    </div>
  )
}
