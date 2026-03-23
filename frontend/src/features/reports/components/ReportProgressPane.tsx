import { motion, useReducedMotion, AnimatePresence } from 'framer-motion'
import { Globe, Search, Tag, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/Badge'
import { HorizontalStepper } from '@/features/reports/components/HorizontalStepper'
import type { PipelineEvent } from '@/lib/types/research'
import type { LoadPhase } from './useReportLifecycle'

interface PreviewData {
  appType?: string
  keywords?: string[]
  targetScenario?: string
  sourcePreviews: { platform: string; count: number }[]
  competitorCount?: number
}

function derivePreview(events: PipelineEvent[]): PreviewData {
  const preview: PreviewData = { sourcePreviews: [] }

  for (const event of events) {
    if (event.type === 'intent_parsed') {
      const data = event.data as Record<string, unknown>
      preview.appType = data.app_type as string | undefined
      preview.keywords = data.keywords as string[] | undefined
      preview.targetScenario = data.target_scenario as string | undefined
    }

    if (event.type === 'source_completed') {
      const count = (event.data?.count as number) ?? 0
      const platform = (event.data?.platform as string) ?? event.stage.replace('_search', '')
      preview.sourcePreviews.push({ platform, count })
    }

    if (event.type === 'extraction_completed') {
      const count = event.data?.count as number | undefined
      if (count !== undefined) {
        preview.competitorCount = (preview.competitorCount ?? 0) + count
      }
    }
  }

  return preview
}

function ProgressPreview({ events }: { events: PipelineEvent[] }) {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const preview = derivePreview(events)
  const hasContent = preview.appType || preview.sourcePreviews.length > 0

  if (!hasContent) {
    return (
      <div className="max-w-xl mx-auto space-y-4 mt-6">
        <motion.div
          initial={reduceMotion ? false : { opacity: 0, y: 10 }}
          animate={reduceMotion ? false : { opacity: 1, y: 0 }}
          className="rounded-none border-2 border-border border-dashed bg-card/50 p-8 flex flex-col items-center justify-center text-center space-y-4"
        >
          <div className="w-6 h-6 rounded-full border-2 border-border border-t-cta animate-spin" />
          <p className="text-xs text-muted-foreground">{t('report.progress.initializing', 'Connecting to analysis engine...')}</p>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto space-y-4 mt-6">
      {preview.appType && (
        <motion.div
          layout={!reduceMotion}
          initial={reduceMotion ? false : { opacity: 0, x: 20 }}
          animate={reduceMotion ? false : { opacity: 1, x: 0 }}
          transition={reduceMotion ? undefined : { duration: 0.4 }}
          className="rounded-none border-2 border-border bg-card shadow p-6 relative overflow-hidden"
        >
          <p className="text-xs font-medium text-muted-foreground mb-4">{t('report.progress.ideaProfile')}</p>
          <div className="flex flex-wrap gap-2">
            <Badge variant="accent" className="max-w-full py-0.5">
              <Globe className="w-3 h-3 shrink-0" />
              <span className="truncate">{preview.appType}</span>
            </Badge>
            {preview.keywords?.map((keyword, index) => (
              <Badge key={index} variant="default" className="max-w-full py-0.5">
                <Tag className="w-3 h-3 shrink-0" />
                <span className="truncate">{keyword}</span>
              </Badge>
            ))}
          </div>
          {preview.targetScenario && (
            <p className="text-xs text-muted-foreground mt-2 break-words">{preview.targetScenario}</p>
          )}
        </motion.div>
      )}

      {preview.sourcePreviews.length > 0 && (
        <motion.div
          layout={!reduceMotion}
          initial={reduceMotion ? false : { opacity: 0, x: 20 }}
          animate={reduceMotion ? false : { opacity: 1, x: 0 }}
          transition={reduceMotion ? undefined : { duration: 0.4, delay: 0.1 }}
          className="rounded-none border-2 border-border bg-card shadow p-6 mt-5 overflow-hidden"
        >
          <p className="text-xs font-medium text-muted-foreground mb-2">{t('report.progress.searchResults')}</p>
          <motion.div layout={!reduceMotion} className="space-y-0">
            <AnimatePresence initial={false}>
              {preview.sourcePreviews.map((sourcePreview) => (
                <motion.div
                  key={sourcePreview.platform}
                  initial={reduceMotion ? false : { opacity: 0, height: 0, marginTop: 0 }}
                  animate={reduceMotion ? false : { opacity: 1, height: 'auto', marginTop: 6 }}
                  className="flex items-center gap-2 text-xs overflow-hidden"
                >
                  <Search className="w-3 h-3 text-cta shrink-0" />
                  <span className="text-muted-foreground truncate">
                    {t('report.progress.foundResults', { count: sourcePreview.count })}{' '}
                    <span className="font-medium text-foreground capitalize">{sourcePreview.platform}</span>
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
          {preview.competitorCount !== undefined && (
            <motion.p
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={reduceMotion ? false : { opacity: 1 }}
              className="text-xs text-cta mt-4 font-medium"
            >
              {t('report.progress.potentialCompetitors', { count: preview.competitorCount })}
            </motion.p>
          )}
        </motion.div>
      )}
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
    <div>
      <HorizontalStepper events={events} isReconnecting={isReconnecting} />
      <ProgressPreview events={events} />
      {(loadPhase === 'processing' || !reportId) && !isComplete && (
        <div className="flex justify-center mt-4">
          <button
            onClick={onCancel}
            className="inline-flex items-center justify-center min-h-[44px] min-w-[44px] gap-1.5 px-4 py-2 text-xs text-muted-foreground rounded-none border-2 border-border cursor-pointer transition-colors duration-200 hover:text-danger hover:border-danger/30"
          >
            <XCircle className="w-3.5 h-3.5" />
            {t('report.progress.cancel')}
          </button>
        </div>
      )}
    </div>
  )
}
