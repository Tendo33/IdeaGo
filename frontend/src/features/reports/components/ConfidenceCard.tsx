import { ShieldCheck, AlertTriangle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ConfidenceMetrics } from '@/lib/types/research'

interface ConfidenceCardProps {
  confidence: ConfidenceMetrics | null | undefined
}

function getConfidenceTone(score: number): {
  badgeClass: string
  progressClass: string
  labelKey: string
  suggestionKey: string
} {
  if (score >= 75) {
    return {
      badgeClass: 'bg-cta/15 text-cta border-cta/30',
      progressClass: 'bg-cta',
      labelKey: 'report.transparency.confidence.high',
      suggestionKey: 'report.transparency.confidence.suggestionHigh',
    }
  }
  if (score >= 45) {
    return {
      badgeClass: 'bg-warning/15 text-warning border-warning/30',
      progressClass: 'bg-warning',
      labelKey: 'report.transparency.confidence.medium',
      suggestionKey: 'report.transparency.confidence.suggestionMedium',
    }
  }
  return {
    badgeClass: 'bg-danger/15 text-danger border-danger/30',
    progressClass: 'bg-danger',
    labelKey: 'report.transparency.confidence.low',
    suggestionKey: 'report.transparency.confidence.suggestionLow',
  }
}

export function ConfidenceCard({ confidence }: ConfidenceCardProps) {
  const { t } = useTranslation()
  const hasConfidence = Boolean(confidence && typeof confidence === 'object')
  const score = toBoundedInt(confidence?.score, 0, 100)
  const successRate = toBoundedInt((confidence?.source_success_rate ?? 0) * 100, 0, 100)
  const sampleSize = toBoundedInt(confidence?.sample_size, 0, 99999)
  const sourceCoverage = toBoundedInt(confidence?.source_coverage, 0, 999)
  const freshnessHint = confidence?.freshness_hint?.trim() || t('report.transparency.confidence.defaultFreshness')
  const tone = getConfidenceTone(score)

  return (
    <div className="card space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold font-heading text-foreground inline-flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-cta" />
          {t('report.transparency.confidence.title')}
        </h3>
        <span className={`px-2.5 py-1 text-xs rounded-none border ${tone.badgeClass}`}>
          {t(tone.labelKey)}
        </span>
      </div>

      <div className="mb-4">
        <div className="flex items-end justify-between gap-3 mb-3">
          <p className="text-xs text-muted-foreground break-words">{t('report.transparency.confidence.score')}</p>
          <p className="text-lg font-bold text-foreground shrink-0">{score}/100</p>
        </div>
        <div className="h-2 rounded-none bg-secondary overflow-hidden">
          <div className={`h-2 ${tone.progressClass} transition-all duration-1000 ease-out-expo`} style={{ width: `${score}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-none border-2 border-border bg-muted/30 hover:bg-muted/70 transition-colors duration-200 p-3 flex flex-col justify-between">
          <p className="text-xs text-muted-foreground break-words">{t('report.transparency.confidence.samples')}</p>
          <p className="text-base font-bold text-foreground mt-2">{sampleSize}</p>
        </div>
        <div className="rounded-none border-2 border-border bg-muted/30 hover:bg-muted/70 transition-colors duration-200 p-3 flex flex-col justify-between">
          <p className="text-xs text-muted-foreground break-words">{t('report.transparency.confidence.coverage')}</p>
          <p className="text-base font-bold text-foreground mt-2">{sourceCoverage}</p>
        </div>
        <div className="rounded-none border-2 border-border bg-muted/30 hover:bg-muted/70 transition-colors duration-200 p-3 flex flex-col justify-between">
          <p className="text-xs text-muted-foreground break-words">{t('report.transparency.confidence.successRate')}</p>
          <p className="text-base font-bold text-foreground mt-2">{successRate}%</p>
        </div>
      </div>

      <div className="rounded-none border-2 border-border bg-muted/55 p-4">
        <p className="text-xs text-muted-foreground break-words">{freshnessHint}</p>
      </div>

      <p className="mt-4 text-sm text-muted-foreground flex items-start gap-2 break-words leading-relaxed">
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <span>{t(tone.suggestionKey)}</span>
      </p>
      {!hasConfidence && (
        <p className="mt-2 text-xs text-warning">{t('report.transparency.unavailable')}</p>
      )}
    </div>
  )
}

function toBoundedInt(value: number | undefined, min: number, max: number): number {
  const normalized = Number(value)
  if (!Number.isFinite(normalized)) {
    return min
  }
  return Math.max(min, Math.min(max, Math.round(normalized)))
}
