import { motion, AnimatePresence } from 'framer-motion'
import { Check, Loader2, WifiOff, Clock, AlertCircle, Pause } from 'lucide-react'
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

function ElapsedTime({ elapsed }: { elapsed: number }) {
  const { t } = useTranslation()
  return (
    <span className="flex items-center gap-1.5 tabular-nums font-mono text-xs text-muted-foreground">
      <Clock className="h-3.5 w-3.5 opacity-70" />
      {t('report.stepper.elapsed', { elapsed })}
    </span>
  )
}

function AnimatedElapsedTimeContainer({ isDone }: { isDone: boolean }) {
  const elapsed = useElapsed(!isDone)

  return (
    <AnimatePresence mode="wait">
      {!isDone && (
        <motion.div
          key="runtime"
          initial={{ opacity: 0, filter: 'blur(4px)' }}
          animate={{ opacity: 1, filter: 'blur(0px)' }}
          exit={{ opacity: 0, filter: 'blur(4px)' }}
          className="flex items-center"
        >
          <ElapsedTime elapsed={elapsed} />
        </motion.div>
      )}
    </AnimatePresence>
  )
}

interface HorizontalStepperProps {
  events: PipelineEvent[]
  isReconnecting?: boolean
}

function StepIndicator({ status }: { status: ProgressStepStatus }) {
  if (status === 'done') {
    return (
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-foreground text-background shadow-sm">
        <Check className="h-3.5 w-3.5" />
      </div>
    )
  }

  if (status === 'active') {
    return (
      <div className="relative flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <div className="absolute inset-0 rounded-full bg-primary/20 animate-ping opacity-50" />
        <Loader2 className="h-3.5 w-3.5 animate-spin relative z-10" />
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-danger/10 text-danger">
        <AlertCircle className="h-3.5 w-3.5" />
      </div>
    )
  }

  if (status === 'cancelled') {
    return (
      <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Pause className="h-3.5 w-3.5" />
      </div>
    )
  }

  return (
    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border/60 bg-background/50">
      <div className="h-1.5 w-1.5 rounded-full bg-border" />
    </div>
  )
}

export function HorizontalStepper({ events, isReconnecting = false }: HorizontalStepperProps) {
  const { t } = useTranslation()
  const { steps } = deriveProgressModel(events, t)
  const isDone = ['done', 'failed', 'cancelled'].includes(steps.at(-1)?.status ?? '')
  const activeIndex = steps.findIndex(step => step.status === 'active')
  const progressIndex = activeIndex >= 0
    ? activeIndex
    : steps.reduce((lastIndex, step, index) => (
      step.status !== 'pending' ? index : lastIndex
    ), 0)

  const progressRatio = steps.length > 1 ? Math.max(0, Math.min(1, progressIndex / (steps.length - 1))) : 0

  return (
    <div className="w-full">
      <AnimatePresence>
        {isReconnecting && (
          <motion.div
            initial={{ opacity: 0, height: 0, marginBottom: 0 }}
            animate={{ opacity: 1, height: 'auto', marginBottom: 24 }}
            exit={{ opacity: 0, height: 0, marginBottom: 0 }}
            className="flex items-center gap-2 border border-warning/20 bg-warning/5 px-4 py-3 text-xs text-warning rounded-sm"
            role="alert"
          >
            <WifiOff className="w-4 h-4 shrink-0" aria-hidden="true" />
            <span className="font-medium tracking-wide">{t('report.stepper.reconnecting')}</span>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-col gap-10">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.3em] text-muted-foreground/60">
              {t('report.progress.eyebrow')}
            </h3>
            <p className="text-lg text-foreground font-medium max-w-xl">
              {t('report.progress.pipelineSummary')}
            </p>
          </div>
          <AnimatedElapsedTimeContainer isDone={isDone} />
        </div>

        <div className="relative overflow-x-auto no-scrollbar pb-4 pt-4 -mt-4">
          <div className="min-w-[600px] relative">
            {/* Progress Track */}
            <div className="absolute top-[11px] left-[20px] right-[20px] h-[1px] bg-border/40">
              <motion.div
                className="h-full bg-primary origin-left"
                initial={{ scaleX: 0 }}
                animate={{ scaleX: progressRatio }}
                transition={{ duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
              />
            </div>

            {/* Steps */}
            <div className="relative z-10 flex justify-between">
              {steps.map((step, idx) => {
                const isPast = idx <= progressIndex && step.status !== 'active'
                const isActive = step.status === 'active'

                return (
                  <div key={step.id} className="flex flex-col items-center gap-4 w-full group">
                    <div className="bg-background px-4 z-10 transition-transform duration-500 group-hover:scale-110">
                      <StepIndicator status={step.status} />
                    </div>
                    <div className="text-center space-y-1.5 px-2">
                      <p
                        className={`text-[13px] font-medium tracking-wide transition-all duration-300 ${
                          isActive
                            ? 'text-primary'
                            : isPast
                              ? 'text-foreground'
                              : 'text-muted-foreground/40'
                        }`}
                      >
                        {step.shortLabel}
                      </p>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
