import { motion, useReducedMotion, AnimatePresence } from 'framer-motion'
import type { TFunction } from 'i18next'
import { Activity, ArrowRight, Radar, Tag, Target, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/Badge'
import { HorizontalStepper } from '@/features/reports/components/HorizontalStepper'
import { PlatformIcon, platformColors } from '@/features/reports/components/PlatformIcons'
import type { PipelineEvent, Platform } from '@/lib/types/research'
import { deriveProgressModel, type ProgressStepStatus } from './progressModel'
import type { LoadPhase } from './useReportLifecycle'

function isKnownPlatform(platform: string): platform is Platform {
  return platform in PlatformIcon
}

function getSourceToneClasses(status: ProgressStepStatus): string {
  switch (status) {
    case 'done':
      return 'bg-muted/50 text-foreground'
    case 'active':
      return 'border-primary/20 bg-primary/10 text-primary'
    case 'failed':
      return 'border-danger/20 bg-danger/10 text-danger'
    case 'cancelled':
      return 'bg-muted/30 text-muted-foreground'
    default:
      return 'bg-card text-foreground'
  }
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

function getFeedToneClasses(tone: 'neutral' | 'live' | 'success' | 'danger' | 'muted'): string {
  switch (tone) {
    case 'live':
      return 'bg-primary/10 text-primary'
    case 'success':
      return 'bg-success/10 text-success'
    case 'danger':
      return 'bg-danger/10 text-danger'
    case 'muted':
      return 'bg-muted/30 text-muted-foreground'
    default:
      return 'bg-transparent text-foreground'
  }
}

function ProgressPreview({ events }: { events: PipelineEvent[] }) {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const model = deriveProgressModel(events, t)
  const hasIdeaProfileContent = Boolean(model.appType || model.targetScenario || model.keywords.length > 0)
  const totalSources = model.sourcePreviews.length

  return (
    <div className="mt-6 border border-border bg-card shadow-sm">
      <div className="grid gap-8 p-5 sm:p-6 lg:p-8 xl:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)]">
        <div className="space-y-6">
          <div className="space-y-4 border-b border-border pb-6">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="bg-transparent border-border">
                <Activity className="h-3 w-3" aria-hidden="true" />
                {t('report.progress.focusLabel')}
              </Badge>
              <span className="text-sm font-semibold text-foreground">{model.focusLabel}</span>
            </div>

            <AnimatePresence mode="wait">
              <motion.div
                key={`${model.currentStage}-${model.focusLabel}`}
                initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                animate={reduceMotion ? false : { opacity: 1, y: 0 }}
                exit={reduceMotion ? undefined : { opacity: 0, y: -8 }}
                transition={reduceMotion ? undefined : { duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
                className="space-y-2"
                aria-live="polite"
              >
                <h2 className="text-3xl font-semibold leading-[0.92] text-foreground sm:text-4xl">
                  {model.currentTitle}
                </h2>
                <p className="max-w-2xl text-sm leading-6 text-muted-foreground sm:text-[15px]">
                  {model.currentDescription}
                </p>
              </motion.div>
            </AnimatePresence>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="bg-muted/30 px-4 py-3 rounded-sm">
                <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-muted-foreground">
                  {t('report.progress.metrics.sourcesDone')}
                </p>
                <p className="mt-2 text-2xl font-semibold text-foreground">
                  {model.completedSources}
                  <span className="ml-1 text-base text-muted-foreground">/ {totalSources}</span>
                </p>
              </div>
              <div className="bg-muted/30 px-4 py-3 rounded-sm">
                <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-muted-foreground">
                  {t('report.progress.metrics.extracted')}
                </p>
                <p className="mt-2 text-2xl font-semibold text-foreground">
                  {model.aggregationCount ?? model.extractionCount}
                </p>
              </div>
              <div className="bg-muted/30 px-4 py-3 rounded-sm">
                <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-muted-foreground">
                  {t('report.progress.metrics.activeSources')}
                </p>
                <p className="mt-2 text-2xl font-semibold text-foreground">{model.activeSources}</p>
              </div>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
            <section className="space-y-4">
              <div className="flex items-center gap-2">
                <Radar className="h-4 w-4 text-primary" aria-hidden="true" />
                <p className="text-sm font-semibold text-foreground">{t('report.progress.ideaProfile')}</p>
              </div>

              {hasIdeaProfileContent ? (
                <motion.div
                  layout={!reduceMotion}
                  initial={reduceMotion ? false : { opacity: 0, y: 14 }}
                  animate={reduceMotion ? false : { opacity: 1, y: 0 }}
                  className="space-y-4 bg-muted/20 p-4 rounded-sm"
                >
                  {model.appType && (
                    <div className="space-y-1">
                      <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">
                        {t('report.progress.appTypeLabel')}
                      </p>
                      <Badge variant="accent" className="max-w-full py-1">
                        <Activity className="h-3 w-3 shrink-0" aria-hidden="true" />
                        <span className="truncate">{model.appType}</span>
                      </Badge>
                    </div>
                  )}

                  {model.keywords.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">
                        {t('report.progress.keywordsLabel')}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {model.keywords.map(keyword => (
                          <Badge key={keyword} variant="default" className="py-1 whitespace-normal text-left h-auto min-h-[24px]">
                            <Tag className="h-3 w-3 shrink-0" aria-hidden="true" />
                            <span>{keyword}</span>
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {model.targetScenario && (
                    <div className="space-y-2 border-t border-border/50 pt-4">
                      <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-muted-foreground">
                        {t('report.progress.targetScenarioLabel')}
                      </p>
                      <div className="flex items-start gap-2 text-sm leading-6 text-foreground">
                        <Target className="mt-1 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                        <p>{model.targetScenario}</p>
                      </div>
                    </div>
                  )}
                </motion.div>
              ) : (
                <div className="border border-dashed border-border bg-transparent p-4 text-sm leading-6 text-muted-foreground rounded-sm">
                  {t('report.progress.waiting.description')}
                </div>
              )}
            </section>

            <section className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Activity className="h-4 w-4 text-primary" aria-hidden="true" />
                  <p className="text-sm font-semibold text-foreground">{t('report.progress.searchResults')}</p>
                </div>
                <span className="text-xs text-muted-foreground">
                  {model.failedSources > 0 ? t('report.progress.failedSources', { count: model.failedSources }) : t('report.progress.allSourcesHealthy')}
                </span>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                {model.sourcePreviews.map((source, index) => {
                  const Icon = isKnownPlatform(source.platform) ? PlatformIcon[source.platform] : Activity
                  const colorClass = isKnownPlatform(source.platform) ? platformColors[source.platform] : 'bg-primary/10 text-primary'
                  const displayCount = source.count ?? (source.status === 'done' || source.status === 'failed' ? 0 : '··')

                  return (
                    <motion.div
                      key={source.platform}
                      initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                      animate={reduceMotion ? false : { opacity: 1, y: 0 }}
                      transition={reduceMotion ? undefined : { delay: Math.min(0.04 * index, 0.2), duration: 0.3 }}
                      className={`relative overflow-hidden border px-5 py-4 rounded-sm ${source.status === 'active' || source.status === 'failed' ? 'border-current' : 'border-transparent'} ${getSourceToneClasses(source.status)}`}
                      style={{ willChange: 'transform, opacity' }}
                    >
                      <div className="flex flex-col gap-3">
                        <div className="flex items-center gap-3">
                          <span className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-sm ${colorClass}`}>
                            <Icon className="h-5 w-5" aria-hidden="true" />
                          </span>
                          <div className="flex flex-col">
                            <span className="text-xl font-bold leading-none text-foreground">{displayCount}</span>
                            <span className="mt-1 text-[11px] uppercase tracking-wider opacity-70">
                              {t('report.progress.resultUnit')}
                            </span>
                          </div>
                        </div>

                        <div className="flex items-center justify-between">
                          <p className="truncate text-base font-semibold text-foreground">{source.label}</p>
                          <p className="text-xs font-medium opacity-80">{getStatusLabel(t, source.status)}</p>
                        </div>
                      </div>
                    </motion.div>
                  )
                })}
              </div>

              {model.extractionCount > 0 && (
                <p className="text-sm font-medium text-primary">
                  {t('report.progress.potentialCompetitors', { count: model.aggregationCount ?? model.extractionCount })}
                </p>
              )}
            </section>
          </div>
        </div>

        <aside className="space-y-4 border-t border-border pt-6 xl:border-l xl:border-t-0 xl:pl-8 xl:pt-0">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <ArrowRight className="h-4 w-4 text-primary" aria-hidden="true" />
              <p className="text-sm font-semibold text-foreground">{t('report.progress.timeline')}</p>
            </div>
            <p className="text-sm text-muted-foreground">{t('report.progress.timelineDescription')}</p>
          </div>

          {model.feed.length > 0 ? (
            <motion.ol layout={!reduceMotion} className="space-y-3" aria-live="polite">
              <AnimatePresence initial={false}>
                {model.feed.map((item, index) => (
                  <motion.li
                    key={item.id}
                    layout={!reduceMotion}
                    initial={reduceMotion ? false : { opacity: 0, x: 14 }}
                    animate={reduceMotion ? false : { opacity: 1, x: 0 }}
                    exit={reduceMotion ? undefined : { opacity: 0, x: -10 }}
                    transition={reduceMotion ? undefined : { delay: Math.min(0.03 * index, 0.15), duration: 0.22 }}
                    className={`flex items-start gap-3 px-3 py-3 rounded-sm ${getFeedToneClasses(item.tone)}`}
                    style={{ willChange: 'transform, opacity' }}
                  >
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-background/50 text-[11px] font-bold">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <p className="text-sm leading-6">{item.label}</p>
                  </motion.li>
                ))}
              </AnimatePresence>
            </motion.ol>
          ) : (
            <div className="border border-dashed border-border p-4 text-sm text-muted-foreground rounded-sm">
              {t('report.progress.timelineEmpty')}
            </div>
          )}
        </aside>
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
    <section className="space-y-6">
      <HorizontalStepper events={events} isReconnecting={isReconnecting} />
      <ProgressPreview events={events} />
      {(loadPhase === 'processing' || !reportId) && !isComplete && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-2 border border-border bg-background px-6 py-2.5 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground transition-all duration-200 hover:-translate-y-0.5 hover:text-danger hover:shadow-sm rounded-sm"
            aria-label={t('report.progress.cancel')}
          >
            <XCircle className="h-4 w-4" aria-hidden="true" />
            {t('report.progress.cancel')}
          </button>
        </div>
      )}
    </section>
  )
}
