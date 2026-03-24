import { motion, AnimatePresence } from 'framer-motion'
import { Check, LoaderCircle, WifiOff, Clock, AlertTriangle, Pause } from 'lucide-react'
import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import type { PipelineEvent } from '@/lib/types/research'
import { deriveProgressModel, type ProgressStepStatus } from './progressModel'

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

function StepDot({ status, detail }: { status: ProgressStepStatus; detail?: string }) {
  const base = 'relative flex h-11 w-11 shrink-0 items-center justify-center border border-border/70 bg-background/85 backdrop-blur-none'

  if (status === 'done') {
    return (
      <motion.div
        initial={{ scale: 0.92, opacity: 0.7 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
        className={`${base} text-primary shadow-[4px_4px_0_0_color-mix(in_oklab,var(--color-primary)_20%,transparent)]`}
      >
        <span className="absolute inset-0 bg-primary/8" />
        {detail ? (
          <span className="relative text-[11px] font-black">{detail}</span>
        ) : (
          <Check className="relative h-4 w-4" />
        )}
      </motion.div>
    )
  }

  if (status === 'active') {
    return (
      <motion.div
        animate={{ opacity: [0.75, 1, 0.75] }}
        transition={{ duration: 1.8, repeat: Number.POSITIVE_INFINITY, ease: 'easeInOut' }}
        className={`${base} text-primary`}
      >
        <motion.span
          animate={{ scale: [1, 1.08, 1] }}
          transition={{ duration: 1.8, repeat: Number.POSITIVE_INFINITY, ease: 'easeInOut' }}
          className="absolute inset-0 border border-primary/35"
        />
        <LoaderCircle className="relative h-4 w-4 animate-spin" />
      </motion.div>
    )
  }

  if (status === 'failed') {
    return (
      <div className={`${base} text-danger`}>
        <span className="absolute inset-0 bg-danger/10" />
        <AlertTriangle className="relative h-4 w-4" />
      </div>
    )
  }

  if (status === 'cancelled') {
    return (
      <div className={`${base} text-muted-foreground`}>
        <span className="absolute inset-0 bg-muted/60" />
        <Pause className="relative h-4 w-4" />
      </div>
    )
  }

  return (
    <div className={`${base} text-muted-foreground/80`}>
      <span className="h-2 w-2 rounded-full border border-current" />
    </div>
  )
}

export function HorizontalStepper({ events, isReconnecting = false }: HorizontalStepperProps) {
  const { t } = useTranslation()
  const { steps } = deriveProgressModel(events, t)
  const isDone = ['done', 'failed', 'cancelled'].includes(steps.at(-1)?.status ?? '')
  const elapsed = useElapsed(!isDone)
  const activeIndex = steps.findIndex(step => step.status === 'active')
  const progressIndex = activeIndex >= 0
    ? activeIndex
    : steps.reduce((lastIndex, step, index) => (
      step.status !== 'pending' ? index : lastIndex
    ), 0)
  const progressRatio = steps.length > 1 && progressIndex >= 0 ? progressIndex / (steps.length - 1) : 0
  const progressScale = Math.max(0.06, progressRatio)

  return (
    <div className="w-full">
      {isReconnecting && (
        <div className="mb-4 flex max-w-md items-center gap-2 border border-warning/35 bg-warning/10 px-3 py-2 text-xs text-warning">
          <WifiOff className="w-3.5 h-3.5 shrink-0" />
          {t('report.stepper.reconnecting')}
        </div>
      )}

      <div className="relative overflow-hidden border border-border/70 bg-background/70 px-4 py-5 sm:px-5">
        <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-1">
            <p className="text-[10px] font-bold uppercase tracking-[0.28em] text-muted-foreground">
              {t('report.progress.eyebrow')}
            </p>
            <p className="max-w-xl text-sm text-muted-foreground">
              {t('report.progress.pipelineSummary')}
            </p>
          </div>

          <AnimatePresence mode="wait">
            {!isDone && (
              <motion.div
                key="runtime"
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground"
              >
                <span className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  {t('report.stepper.elapsed', { elapsed })}
                </span>
                <span>{t('report.stepper.usually')}</span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="relative overflow-x-auto pb-2">
          <div className="absolute left-0 right-0 top-5 h-px bg-border/30" />
          <motion.div
            className="absolute left-0 right-0 top-5 h-px origin-left bg-primary/70"
            animate={{ scaleX: progressScale }}
            transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          />
          <div className="relative flex min-w-[860px] items-start justify-between gap-3">
            {steps.map(step => (
              <div key={step.id} className="flex max-w-[92px] min-w-[76px] flex-1 flex-col items-center gap-3 text-center">
                <StepDot status={step.status} detail={step.detail} />
                <div className="space-y-1">
                  <p
                    className={`text-[11px] font-semibold leading-tight transition-colors ${
                      step.status === 'active'
                        ? 'text-primary'
                        : step.status === 'done'
                          ? 'text-foreground'
                          : step.status === 'failed'
                            ? 'text-danger'
                            : step.status === 'cancelled'
                              ? 'text-muted-foreground'
                              : 'text-muted-foreground'
                    }`}
                  >
                    {step.shortLabel}
                  </p>
                  <p className="text-[10px] leading-tight text-muted-foreground/85">{step.label}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <AnimatePresence>
        {!isDone && (
          <motion.div
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="sr-only"
          >
            {t('report.stepper.elapsed', { elapsed })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
