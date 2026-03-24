import { AlertTriangle, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ConfidenceMetrics } from '@/lib/types/research'

export interface ConfidenceCardProps {
  confidence: ConfidenceMetrics | null | undefined
}

interface ToneConfig {
  badgeClass: string
  progressClass: string
  labelKey: string
  suggestionKey: string
}

interface MetricRow {
  label: string
  value: string
}

function getConfidenceTone(score: number): ToneConfig {
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

  if (!hasConfidence) {
    return (
      <div className="card space-y-4">
        <div className="flex items-center justify-between gap-4">
          <h3 className="inline-flex items-center gap-2 text-sm font-semibold font-heading text-foreground">
            <ShieldCheck className="h-4 w-4 text-cta" />
            {t('report.transparency.confidence.title')}
          </h3>
          <span className="rounded-none border border-warning/30 bg-warning/15 px-2.5 py-1 text-xs text-warning">
            {t('report.transparency.unavailable')}
          </span>
        </div>
        <div className="rounded-none border-2 border-border bg-muted/40 p-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t('report.transparency.unavailable')}
          </p>
        </div>
      </div>
    )
  }

  const score = toBoundedInt(confidence?.score, 0, 100)
  const successRate = toBoundedInt((confidence?.source_success_rate ?? 0) * 100, 0, 100)
  const sampleSize = toBoundedInt(confidence?.sample_size, 0, 99999)
  const sourceCoverage = toBoundedInt(confidence?.source_coverage, 0, 999)
  const sourceDiversity = toBoundedInt(confidence?.source_diversity, 0, 999)
  const evidenceDensity = toBoundedInt((confidence?.evidence_density ?? 0) * 100, 0, 100)
  const recencyScore = toBoundedInt((confidence?.recency_score ?? 0) * 100, 0, 100)
  const degradationPenalty = toBoundedInt((confidence?.degradation_penalty ?? 0) * 100, 0, 100)
  const contradictionPenalty = toBoundedInt((confidence?.contradiction_penalty ?? 0) * 100, 0, 100)
  const freshnessHint =
    confidence?.freshness_hint?.trim() || t('report.transparency.confidence.defaultFreshness')
  const reasons = Array.isArray(confidence?.reasons)
    ? confidence.reasons.filter(reason => reason.trim().length > 0)
    : []
  const tone = getConfidenceTone(score)

  const primaryMetrics: MetricRow[] = [
    { label: t('report.transparency.confidence.samples'), value: String(sampleSize) },
    { label: t('report.transparency.confidence.coverage'), value: String(sourceCoverage) },
    { label: t('report.transparency.confidence.successRate'), value: `${successRate}%` },
    { label: 'Source diversity', value: String(sourceDiversity) },
    { label: 'Evidence density', value: `${evidenceDensity}%` },
    { label: 'Recency', value: `${recencyScore}%` },
  ]

  const penaltyMetrics: MetricRow[] = [
    { label: 'Degradation penalty', value: `${degradationPenalty}%` },
    { label: 'Contradiction penalty', value: `${contradictionPenalty}%` },
  ]
  const hasPenalty = degradationPenalty > 0 || contradictionPenalty > 0

  return (
    <div className="card space-y-6">
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-sm font-semibold font-heading text-foreground inline-flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-cta" />
          {t('report.transparency.confidence.title')}
        </h3>
        <span className={`rounded-none border px-2.5 py-1 text-xs ${tone.badgeClass}`}>
          {t(tone.labelKey)}
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex items-end justify-between gap-3">
          <p className="text-xs text-muted-foreground break-words">
            {t('report.transparency.confidence.score')}
          </p>
          <p className="shrink-0 text-lg font-bold text-foreground">{score}/100</p>
        </div>
        <div className="h-2 overflow-hidden rounded-none bg-secondary">
          <div
            className={`h-2 transition-all duration-1000 ease-out-expo ${tone.progressClass}`}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {primaryMetrics.map(metric => (
          <div
            key={metric.label}
            className="flex min-h-20 flex-col justify-between rounded-none border-2 border-border bg-muted/30 p-3 transition-colors duration-200 hover:bg-muted/70"
          >
            <p className="text-xs text-muted-foreground break-words">{metric.label}</p>
            <p className="mt-2 text-base font-bold text-foreground">{metric.value}</p>
          </div>
        ))}
      </div>

      <div className="rounded-none border-2 border-border bg-muted/55 p-4">
        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Freshness</p>
        <p className="mt-2 text-sm text-foreground break-words">{freshnessHint}</p>
      </div>

      <div className="space-y-3 rounded-none border-2 border-border bg-background p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            Trust Drivers
          </p>
          {hasPenalty ? (
            <span className="rounded-none border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-warning">
              Penalties Applied
            </span>
          ) : (
            <span className="rounded-none border border-cta/30 bg-cta/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-cta">
              No Major Penalties
            </span>
          )}
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          {penaltyMetrics.map(metric => (
            <div
              key={metric.label}
              className="rounded-none border border-border/70 bg-muted/30 px-3 py-2"
            >
              <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                {metric.label}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">{metric.value}</p>
            </div>
          ))}
        </div>

        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Why this score</p>
          {reasons.length > 0 ? (
            <ul className="space-y-2">
              {reasons.map(reason => (
                <li
                  key={reason}
                  className="flex items-start gap-2 rounded-none border border-border/70 bg-muted/35 px-3 py-2 text-sm text-foreground"
                >
                  <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cta" />
                  <span className="break-words">{reason}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">
              No specific confidence reasons were provided for this report.
            </p>
          )}
        </div>
      </div>

      <p className="flex items-start gap-2 text-sm leading-relaxed text-muted-foreground">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <span>{t(tone.suggestionKey)}</span>
      </p>
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
