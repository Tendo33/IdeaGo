import { motion, useReducedMotion, AnimatePresence } from 'framer-motion'
import type { TFunction } from 'i18next'
import { Activity, CheckCircle2, Hash, Radar, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { HorizontalStepper } from '@/features/reports/components/HorizontalStepper'
import { PlatformIcon } from '@/features/reports/components/PlatformIcons'
import type { PipelineEvent, Platform } from '@/lib/types/research'
import { deriveProgressModel, type ProgressStepStatus } from './progressModel'
import type { LoadPhase } from './useReportLifecycle'

function isKnownPlatform(platform: string): platform is Platform {
  return platform in PlatformIcon
}

function getStatusLabel(t: TFunction, status: ProgressStepStatus): string {
  switch (status) {
    case 'done':
      return t('report.progress.status.done')
    case 'active':
      return t('report.progress.status.active')
    case 'failed':
      return t('report.progress.status.failed')
    case 'cancelled':
      return t('report.progress.status.cancelled')
    default:
      return t('report.progress.status.pending')
  }
}

function ProgressPreview({ events }: { events: PipelineEvent[] }) {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const model = deriveProgressModel(events, t)
  const hasIdeaProfileContent = Boolean(model.appType || model.targetScenario || model.keywords.length > 0)
  const totalSources = model.sourcePreviews.length

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.08 }
    }
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 15, filter: 'blur(4px)' },
    show: {
      opacity: 1, y: 0, filter: 'blur(0px)',
      transition: { type: 'spring' as const, stiffness: 300, damping: 24 }
    }
  }

  return (
    <div className="grid lg:grid-cols-[1fr_360px] xl:grid-cols-[1fr_400px] gap-16 xl:gap-24 items-start pt-6 pb-20">

      {/* Left Column: Big typography & Metrics & Source tracking */}
      <div className="flex flex-col gap-16">

        {/* Giant Hero Section */}
        <div className="space-y-8">
          <AnimatePresence mode="wait">
            <motion.div
              key={`${model.currentStage}-${model.focusLabel}`}
              initial={reduceMotion ? false : { opacity: 0, y: 10 }}
              animate={reduceMotion ? false : { opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -10 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              className="space-y-5"
            >
              <div className="inline-flex items-center justify-center px-3 py-1 rounded-full bg-primary/5 text-primary text-[10px] font-bold uppercase tracking-[0.25em]">
                {model.focusLabel}
              </div>
              <h2 className="text-4xl sm:text-5xl lg:text-6xl font-semibold tracking-tight text-foreground leading-[1.05]">
                {model.currentTitle}
              </h2>
              <p className="text-base sm:text-lg text-muted-foreground/80 font-medium leading-relaxed max-w-2xl">
                {model.currentDescription}
              </p>
            </motion.div>
          </AnimatePresence>

          {/* Metric Numbers */}
          <div className="flex flex-wrap gap-x-12 gap-y-8 pt-4">
            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted-foreground/50">
                {t('report.progress.metrics.sourcesDone')}
              </span>
              <div className="flex items-baseline gap-1.5">
                <span className="text-5xl font-light font-mono tracking-tighter text-foreground">{model.completedSources}</span>
                <span className="text-xl text-muted-foreground/40 font-light font-mono">/ {totalSources}</span>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted-foreground/50">
                {t('report.progress.metrics.extracted')}
              </span>
              <span className="text-5xl font-light font-mono tracking-tighter text-foreground">
                {model.aggregationCount ?? model.extractionCount}
              </span>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted-foreground/50">
                {t('report.progress.metrics.activeSources')}
              </span>
              <span className="text-5xl font-light font-mono tracking-tighter text-foreground">{model.activeSources}</span>
            </div>
          </div>
        </div>

        {/* Dynamic Source Tracking List (Staggered) */}
        <div className="space-y-8">
          <div className="flex items-center justify-between">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted-foreground/60 flex items-center gap-2">
              <Activity className="h-3.5 w-3.5" />
              {t('report.progress.searchResults')}
            </h3>
            {model.failedSources > 0 && (
              <span className="text-[10px] text-danger font-medium uppercase tracking-widest bg-danger/5 px-2 py-0.5 rounded-full">
                {t('report.progress.failedSources', { count: model.failedSources })}
              </span>
            )}
          </div>

          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="show"
            className="flex flex-col gap-0.5"
          >
            {model.sourcePreviews.map((source) => {
              const Icon = isKnownPlatform(source.platform) ? PlatformIcon[source.platform] : Activity
              const displayCount = source.count ?? (source.status === 'done' || source.status === 'failed' ? 0 : '—')

              const isActive = source.status === 'active'
              const isDone = source.status === 'done'
              const isFailed = source.status === 'failed'

              return (
                <motion.div
                  key={source.platform}
                  variants={itemVariants}
                  className={`group relative flex items-center justify-between py-4 px-4 -mx-4 rounded-xl transition-all duration-500 ${
                    isActive
                      ? 'bg-primary/5 scale-[1.02] shadow-[0_8px_30px_rgba(0,0,0,0.04)] z-10'
                      : 'hover:bg-muted/30'
                  }`}
                >
                  <div className="flex items-center gap-5 min-w-0">
                    <div className={`flex items-center justify-center h-10 w-10 rounded-full transition-colors duration-500 ${
                      isActive ? 'bg-primary/20 text-primary' : isDone ? 'bg-transparent text-foreground/80' : isFailed ? 'bg-danger/10 text-danger' : 'bg-transparent text-muted-foreground/40'
                    }`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="flex flex-col min-w-0 gap-1.5">
                      <span className={`text-base font-medium truncate transition-colors duration-500 ${isActive ? 'text-foreground' : 'text-muted-foreground'}`}>
                        {source.label}
                      </span>
                      <span className={`text-[10px] uppercase tracking-widest transition-colors duration-500 ${isActive ? 'text-primary' : isFailed ? 'text-danger' : 'text-muted-foreground/50'}`}>
                        {getStatusLabel(t, source.status)}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col items-end pl-4 gap-1">
                    <span className={`text-3xl font-light font-mono leading-none transition-colors duration-500 ${isActive ? 'text-primary' : 'text-foreground/80'}`}>
                      {displayCount}
                    </span>
                    <span className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground/50">
                      {t('report.progress.resultUnit')}
                    </span>
                  </div>
                </motion.div>
              )
            })}
          </motion.div>

          {model.extractionCount > 0 && (
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              className="flex items-center gap-2 pt-4 text-sm text-primary font-medium"
            >
              <CheckCircle2 className="h-4 w-4" />
              {t('report.progress.potentialCompetitors', { count: model.aggregationCount ?? model.extractionCount })}
            </motion.div>
          )}
        </div>
      </div>

      {/* Right Column: Timeline & Profile (Floating look) */}
      <div className="flex flex-col gap-16 sticky top-8">

        {/* Idea Profile Metadata */}
        {hasIdeaProfileContent && (
          <div className="space-y-6">
            <h3 className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted-foreground/60 flex items-center gap-2">
              <Radar className="h-3.5 w-3.5" />
              {t('report.progress.ideaProfile')}
            </h3>

            <div className="flex flex-col gap-6">
              {model.appType && (
                <div className="space-y-2">
                  <p className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground/50 font-semibold">
                    {t('report.progress.appTypeLabel')}
                  </p>
                  <div className="text-sm font-medium text-foreground">
                    {model.appType}
                  </div>
                </div>
              )}

              {model.keywords.length > 0 && (
                <div className="space-y-2.5">
                  <p className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground/50 font-semibold">
                    {t('report.progress.keywordsLabel')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {model.keywords.map(keyword => (
                      <span key={keyword} className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                        <Hash className="h-3 w-3 opacity-40" />
                        {keyword}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {model.targetScenario && (
                <div className="space-y-2">
                  <p className="text-[9px] uppercase tracking-[0.2em] text-muted-foreground/50 font-semibold">
                    {t('report.progress.targetScenarioLabel')}
                  </p>
                  <div className="text-sm text-muted-foreground leading-relaxed">
                    {model.targetScenario}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Timeline Log */}
        <div className="space-y-8">
          <h3 className="text-[10px] font-bold uppercase tracking-[0.25em] text-muted-foreground/60 flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
            {t('report.progress.timeline')}
          </h3>

          <div className="flex flex-col gap-5 relative before:absolute before:inset-y-0 before:left-[11px] before:w-[1px] before:bg-gradient-to-b before:from-border before:to-transparent">
            <AnimatePresence mode="popLayout" initial={false}>
              {model.feed.length > 0 ? (
                model.feed.map((item, index) => {
                  const isLatest = index === 0;
                  return (
                    <motion.div
                      key={item.id}
                      layout
                      initial={{ opacity: 0, x: 20, filter: 'blur(4px)' }}
                      animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
                      exit={{ opacity: 0, scale: 0.95, filter: 'blur(4px)' }}
                      transition={{
                        type: 'spring', stiffness: 400, damping: 30,
                        opacity: { duration: 0.3 }
                      }}
                      className={`relative pl-8 flex flex-col gap-1 transition-opacity duration-500 ${
                        isLatest ? 'opacity-100' : 'opacity-40 hover:opacity-100'
                      }`}
                    >
                      <div className={`absolute left-0 top-1.5 h-6 w-6 rounded-full border-[3px] border-background flex items-center justify-center ${isLatest ? 'bg-primary' : 'bg-muted-foreground/30'}`}>
                        <div className="h-1.5 w-1.5 rounded-full bg-background" />
                      </div>
                      <span className={`text-[10px] font-mono tracking-widest ${isLatest ? 'text-primary' : 'text-muted-foreground/60'}`}>
                        STEP {String(model.feed.length - index).padStart(2, '0')}
                      </span>
                      <p className={`text-sm leading-relaxed ${isLatest ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                        {item.label}
                      </p>
                    </motion.div>
                  )
                })
              ) : (
                <div className="pl-8 text-xs text-muted-foreground/50 italic">
                  {t('report.progress.timelineEmpty')}
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>

      </div>
    </div>
  )
}

interface ReportProgressPaneProps {
  show: boolean
  events: PipelineEvent[]
  isReconnecting: boolean
  loadPhase: LoadPhase
  isComplete: boolean
  reportId: string | undefined
  onCancel: () => void
}

export function ReportProgressPane({
  show,
  events,
  isReconnecting,
  loadPhase,
  isComplete,
  reportId,
  onCancel,
}: ReportProgressPaneProps) {
  const { t } = useTranslation()
  if (!show) return null

  return (
    <section className="flex flex-col gap-12 max-w-[1200px] mx-auto w-full px-4 sm:px-6 lg:px-8 pt-8">
      <HorizontalStepper events={events} isReconnecting={isReconnecting} />

      <div className="w-full h-px bg-border/40" />

      <ProgressPreview events={events} />

      {(loadPhase === 'processing' || !reportId) && !isComplete && (
        <div className="flex justify-center pb-24">
          <button
            type="button"
            onClick={onCancel}
            className="group inline-flex items-center gap-2 px-6 py-3 rounded-full text-[11px] font-bold uppercase tracking-[0.2em] text-muted-foreground transition-all duration-300 hover:text-danger hover:bg-danger/5"
            aria-label={t('report.progress.cancel')}
          >
            <XCircle className="h-4 w-4 transition-transform group-hover:scale-110" />
            {t('report.progress.cancel')}
          </button>
        </div>
      )}
    </section>
  )
}
