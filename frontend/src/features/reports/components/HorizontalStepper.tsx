import { Check, X, WifiOff, Clock } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import type { PipelineEvent } from '@/lib/types/research'

interface Step {
  id: string
  label: string
  shortLabel: string
  status: 'pending' | 'active' | 'done' | 'failed' | 'cancelled'
  detail?: string
}

const DEFAULT_SOURCE_ORDER = ['github', 'tavily', 'hackernews', 'appstore', 'producthunt'] as const

function getSourcePlatformFromEvent(event: PipelineEvent): string | null {
  const dataPlatform = event.data?.platform
  if (typeof dataPlatform === 'string' && dataPlatform.trim()) {
    return dataPlatform.trim().toLowerCase()
  }

  const stage = event.stage.trim().toLowerCase()
  if (!stage) return null
  if (stage.endsWith('_search')) {
    return stage.slice(0, -'_search'.length)
  }
  const knownPlatform = DEFAULT_SOURCE_ORDER.find(platform => stage.includes(platform))
  return knownPlatform ?? null
}

function getDefaultSourceShortLabel(platform: string): string {
  switch (platform) {
    case 'hackernews':
      return 'HN'
    case 'producthunt':
      return 'PH'
    default:
      return platform
  }
}

function deriveSteps(events: PipelineEvent[], t: TFunction): Step[] {
  const eventSourcePlatforms = events
    .map(getSourcePlatformFromEvent)
    .filter((platform): platform is string => platform !== null)
  const extraPlatforms = Array.from(
    new Set(eventSourcePlatforms.filter(platform => !DEFAULT_SOURCE_ORDER.includes(platform as (typeof DEFAULT_SOURCE_ORDER)[number]))),
  ).sort()
  const orderedPlatforms = [...DEFAULT_SOURCE_ORDER, ...extraPlatforms]

  const steps: Step[] = [
    { id: 'intent', label: t('report.stepper.steps.intent.label'), shortLabel: t('report.stepper.steps.intent.short'), status: 'pending' },
    ...orderedPlatforms.map(platform => ({
      id: platform,
      label: t(`report.stepper.steps.${platform}.label`, { defaultValue: platform }),
      shortLabel: t(`report.stepper.steps.${platform}.short`, { defaultValue: getDefaultSourceShortLabel(platform) }),
      status: 'pending' as const,
    })),
    { id: 'extraction', label: t('report.stepper.steps.extraction.label'), shortLabel: t('report.stepper.steps.extraction.short'), status: 'pending' },
    { id: 'aggregation', label: t('report.stepper.steps.aggregation.label'), shortLabel: t('report.stepper.steps.aggregation.short'), status: 'pending' },
    { id: 'complete', label: t('report.stepper.steps.complete.label'), shortLabel: t('report.stepper.steps.complete.short'), status: 'pending' },
  ]

  const indexByStepId = new Map(steps.map((step, index) => [step.id, index]))
  const updateStep = (
    stepId: string,
    status: Step['status'],
    detail?: string,
  ) => {
    const index = indexByStepId.get(stepId)
    if (index === undefined) return
    steps[index].status = status
    if (detail !== undefined) {
      steps[index].detail = detail
    }
  }

  for (const event of events) {
    switch (event.type) {
      case 'intent_started':
        updateStep('intent', 'active')
        break
      case 'intent_parsed':
        updateStep('intent', 'done')
        break
      case 'source_started':
        {
          const platform = getSourcePlatformFromEvent(event)
          if (platform) updateStep(platform, 'active')
        }
        break
      case 'source_completed': {
        const count = event.data?.count as number | undefined
        const platform = getSourcePlatformFromEvent(event)
        if (platform) {
          updateStep(platform, 'done', count !== undefined ? `${count}` : undefined)
        }
        break
      }
      case 'source_failed':
        {
          const platform = getSourcePlatformFromEvent(event)
          if (platform) updateStep(platform, 'failed')
        }
        break
      case 'extraction_started':
        updateStep('extraction', 'active')
        break
      case 'extraction_completed':
        updateStep('extraction', 'done')
        break
      case 'aggregation_started':
        updateStep('aggregation', 'active')
        break
      case 'aggregation_completed':
        updateStep('aggregation', 'done')
        break
      case 'report_ready':
        updateStep('complete', 'done')
        break
      case 'error':
        updateStep('complete', 'failed')
        break
      case 'cancelled':
        updateStep('complete', 'cancelled')
        break
    }
  }

  return steps
}

function StepDot({ status, detail }: { status: Step['status']; detail?: string }) {
  const base = 'w-7 h-7 rounded-none flex items-center justify-center shrink-0 transition-all duration-300'

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
        <div className={`${base} bg-cta/20 animate-breathing`}>
          <div className="w-2.5 h-2.5 rounded-none bg-cta" />
        </div>
      )
    case 'failed':
      return (
        <div className={`${base} bg-danger/20`}>
          <X className="w-3.5 h-3.5 text-danger" />
        </div>
      )
    case 'cancelled':
      return (
        <div className={`${base} bg-secondary`}>
          <Clock className="w-3.5 h-3.5 text-muted-foreground" />
        </div>
      )
    default:
      return (
        <div className={`${base} bg-border`}>
          <div className="w-1.5 h-1.5 rounded-none bg-text-dim" />
        </div>
      )
  }
}

function Connector({ done }: { done: boolean }) {
  return (
    <div className={`flex-1 h-0.5 mx-0.5 rounded-none transition-colors duration-500 ${done ? 'bg-cta/40' : 'bg-border'}`} />
  )
}

function useElapsed(running: boolean) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!running) return
    const t = setInterval(() => setElapsed(s => s + 1), 1000)
    return () => clearInterval(t)
  }, [running])

  return elapsed
}

interface HorizontalStepperProps {
  events: PipelineEvent[]
  isReconnecting?: boolean
}

export function HorizontalStepper({ events, isReconnecting = false }: HorizontalStepperProps) {
  const { t } = useTranslation()
  const steps = deriveSteps(events, t)
  const isDone = ['done', 'failed', 'cancelled'].includes(steps.at(-1)?.status ?? '')
  const elapsed = useElapsed(!isDone)

  return (
    <div className="w-full py-6">
      {isReconnecting && (
        <div className="flex items-center gap-2 px-3 py-2 mb-4 rounded-none bg-warning/10 border border-warning/30 text-xs text-warning mx-auto max-w-md">
          <WifiOff className="w-3.5 h-3.5 shrink-0" />
          {t('report.stepper.reconnecting')}
        </div>
      )}

      {/* Stepper Row */}
      <div className="flex items-center w-full max-w-3xl mx-auto px-2">
        {steps.map((step, i) => (
          <div key={step.id} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1.5 min-w-0">
              <StepDot status={step.status} detail={step.detail} />
              <span className={`text-[10px] text-center leading-tight truncate max-w-15 transition-colors duration-200 ${
                step.status === 'active' ? 'text-cta font-medium' :
                step.status === 'done' ? 'text-foreground' :
                step.status === 'failed' ? 'text-danger' :
                step.status === 'cancelled' ? 'text-muted-foreground' :
                'text-muted-foreground'
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
        <div className="flex items-center justify-center gap-4 mt-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {t('report.stepper.elapsed', { elapsed })}
          </span>
          <span>{t('report.stepper.usually')}</span>
        </div>
      )}
    </div>
  )
}
