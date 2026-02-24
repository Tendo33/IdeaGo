import { motion } from 'framer-motion'
import { Globe, Search, Tag, XCircle } from 'lucide-react'
import { HorizontalStepper } from '../../components/HorizontalStepper'
import type { PipelineEvent } from '../../types/research'
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
  const preview = derivePreview(events)
  const hasContent = preview.appType || preview.sourcePreviews.length > 0

  if (!hasContent) return null

  return (
    <div className="max-w-xl mx-auto space-y-3 mt-4">
      {preview.appType && (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
          className="rounded-xl border border-border bg-bg-card p-4"
        >
          <p className="text-xs font-medium text-text-dim mb-2">Idea Profile</p>
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-cta/10 text-cta">
              <Globe className="w-3 h-3" />
              {preview.appType}
            </span>
            {preview.keywords?.map((keyword, index) => (
              <span key={index} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-secondary/50 text-text-muted">
                <Tag className="w-3 h-3" />
                {keyword}
              </span>
            ))}
          </div>
          {preview.targetScenario && (
            <p className="text-xs text-text-muted mt-2">{preview.targetScenario}</p>
          )}
        </motion.div>
      )}

      {preview.sourcePreviews.length > 0 && (
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="rounded-xl border border-border bg-bg-card p-4"
        >
          <p className="text-xs font-medium text-text-dim mb-2">Search Results</p>
          <div className="space-y-1.5">
            {preview.sourcePreviews.map((sourcePreview, index) => (
              <div key={index} className="flex items-center gap-2 text-xs">
                <Search className="w-3 h-3 text-cta" />
                <span className="text-text-muted">
                  Found <span className="font-medium text-text">{sourcePreview.count}</span> results from{' '}
                  <span className="font-medium text-text capitalize">{sourcePreview.platform}</span>
                </span>
              </div>
            ))}
          </div>
          {preview.competitorCount !== undefined && (
            <p className="text-xs text-cta mt-2 font-medium">
              {preview.competitorCount} potential competitors identified
            </p>
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
  if (!show) return null

  return (
    <div>
      <HorizontalStepper events={events} isReconnecting={isReconnecting} />
      <ProgressPreview events={events} />
      {loadPhase === 'processing' && !isComplete && reportId && (
        <div className="flex justify-center mt-4">
          <button
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-dim rounded-lg border border-border cursor-pointer transition-colors duration-200 hover:text-danger hover:border-danger/30"
          >
            <XCircle className="w-3.5 h-3.5" />
            Cancel analysis
          </button>
        </div>
      )}
    </div>
  )
}
