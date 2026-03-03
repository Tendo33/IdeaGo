import { ShieldCheck, AlertTriangle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ConfidenceMetrics } from '../types/research'

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
    <div className="card">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h3 className="text-sm font-semibold font-heading text-text inline-flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-cta" />
          {t('report.transparency.confidence.title')}
        </h3>
        <span className={`px-2.5 py-1 text-xs rounded-full border ${tone.badgeClass}`}>
          {t(tone.labelKey)}
        </span>
      </div>

      <div className="mb-3">
        <div className="flex items-end justify-between gap-2 mb-2">
          <p className="text-xs text-text-dim">{t('report.transparency.confidence.score')}</p>
          <p className="text-lg font-bold text-text">{score}/100</p>
        </div>
        <div className="h-2 rounded-full bg-secondary overflow-hidden">
          <div className={`h-2 ${tone.progressClass}`} style={{ width: `${score}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="rounded-lg border border-white/10 bg-white/5 p-2">
          <p className="text-[11px] text-text-dim">{t('report.transparency.confidence.samples')}</p>
          <p className="text-sm font-semibold text-text">{sampleSize}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-2">
          <p className="text-[11px] text-text-dim">{t('report.transparency.confidence.coverage')}</p>
          <p className="text-sm font-semibold text-text">{sourceCoverage}</p>
        </div>
        <div className="rounded-lg border border-white/10 bg-white/5 p-2">
          <p className="text-[11px] text-text-dim">{t('report.transparency.confidence.successRate')}</p>
          <p className="text-sm font-semibold text-text">{successRate}%</p>
        </div>
      </div>

      <div className="rounded-lg border border-white/10 bg-white/5 p-3">
        <p className="text-xs text-text-muted">{freshnessHint}</p>
      </div>

      <p className="mt-3 text-xs text-text-dim inline-flex items-center gap-1.5">
        <AlertTriangle className="w-3.5 h-3.5" />
        {t(tone.suggestionKey)}
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
