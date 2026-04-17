import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { AlertCircle, RefreshCw, Waves } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { startAnalysis } from '@/lib/api/client'
import type { ResearchReport } from '@/lib/types/research'
import { normalizeSourceErrorMessage } from '@/lib/utils/sourceErrorMessage'
import { buttonVariants } from '@/components/ui/Button'
import { broadenQuery } from './query'

export function BlueOceanState({ query }: { query: string }) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [broadenError, setBroadenError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const reduceMotion = useReducedMotion()

  const handleBroaden = async () => {
    if (isSubmitting) return
    setIsSubmitting(true)
    setBroadenError(null)
    try {
      const { report_id } = await startAnalysis(broadenQuery(query))
      navigate(`/reports/${report_id}`)
    } catch (error) {
      setBroadenError(error instanceof Error ? error.message : t('report.error.broaden'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, scale: 0.95 }}
      animate={reduceMotion ? false : { opacity: 1, scale: 1 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
      className="p-12 rounded-none bg-card border-2 border-border text-center shadow"
    >
      <Waves className="w-12 h-12 text-cta mx-auto mb-4" />
      <h3 className="text-xl font-bold font-heading text-foreground mb-2 break-words">{t('report.blueOcean.title')}</h3>
      <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto break-words">
        {t('report.blueOcean.description')}
      </p>
      <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
        <button
          onClick={handleBroaden}
          disabled={isSubmitting}
          className={buttonVariants({ variant: 'primary', size: 'md' })}
          aria-busy={isSubmitting}
        >
          <RefreshCw className={`w-4 h-4 ${isSubmitting ? 'animate-spin' : ''}`} />
          {isSubmitting ? t('report.blueOcean.tryingBroader') : t('report.blueOcean.tryBroader')}
        </button>
      </div>
      <div className="mt-6 text-left max-w-sm mx-auto">
        <p className="text-xs font-medium text-muted-foreground mb-2">{t('report.blueOcean.suggestedSteps')}</p>
        <ol className="space-y-1 text-xs text-muted-foreground list-decimal list-inside">
          <li>{t('report.blueOcean.step1')}</li>
          <li>{t('report.blueOcean.step2')}</li>
          <li>{t('report.blueOcean.step3')}</li>
        </ol>
      </div>
      {broadenError && <p className="mt-4 text-xs text-danger">{broadenError}</p>}
    </motion.div>
  )
}

interface AllFailedStateProps {
  sources: ResearchReport['source_results']
  onRetry: () => void
  isRetrying?: boolean
}

export function AllFailedState({ sources, onRetry, isRetrying = false }: AllFailedStateProps) {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0 }}
      animate={reduceMotion ? false : { opacity: 1 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
      className="p-10 rounded-none bg-card border-2 border-warning text-center shadow"
    >
      <AlertCircle className="w-10 h-10 text-warning mx-auto mb-3" />
      <h3 className="text-lg font-bold font-heading text-foreground mb-3 break-words">{t('report.failed.title')}</h3>
      <div className="space-y-1.5 mb-5 max-w-sm mx-auto">
        {sources.map(source => (
          <div key={source.platform} className="flex items-center justify-between gap-4 text-xs">
            <span className="text-muted-foreground capitalize shrink-0">{source.platform}</span>
            <span className="text-danger text-right break-words min-w-0">
              {normalizeSourceErrorMessage(source.status, source.error_msg) ?? source.status}
            </span>
          </div>
        ))}
      </div>
      <p className="text-xs text-muted-foreground mb-4 break-words">{t('report.failed.description')}</p>
      <button
        onClick={onRetry}
        disabled={isRetrying}
        aria-busy={isRetrying}
        className={buttonVariants({ variant: 'warning', size: 'md' })}
      >
        <RefreshCw className="w-4 h-4" />
        {t('report.failed.retry')}
      </button>
    </motion.div>
  )
}
