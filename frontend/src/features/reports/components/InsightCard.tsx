import { motion, useReducedMotion } from 'framer-motion'
import { ArrowUpRight, Lightbulb, type LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export interface InsightCardProps {
  angle?: string
  index?: number
  eyebrow?: string
  title?: string
  description?: string
  supportingPoints?: string[]
  score?: number | null
  scoreLabel?: string
  icon?: LucideIcon
  tone?: 'default' | 'success' | 'warning'
}

const TONE_STYLES: Record<NonNullable<InsightCardProps['tone']>, string> = {
  default: 'border-cta/20 bg-cta/5 hover:border-cta/40 hover:bg-cta/8',
  success: 'border-success/25 bg-success/8 hover:border-success/45 hover:bg-success/12',
  warning: 'border-warning/25 bg-warning/8 hover:border-warning/45 hover:bg-warning/12',
}

function toPercent(value: number | null | undefined): number | null {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null
  }
  return Math.max(0, Math.min(100, Math.round(value * 100)))
}

function InsightCardBody({
  angle,
  index = 0,
  eyebrow,
  title,
  description,
  supportingPoints,
  score,
  scoreLabel,
  icon: Icon = Lightbulb,
  tone = 'default',
}: InsightCardProps) {
  const { t } = useTranslation()
  const normalizedTitle = title || angle || ''
  const normalizedEyebrow = eyebrow || `${t('report.insight.opportunity')}${index + 1}`
  const metric = toPercent(score)
  const visiblePoints = (supportingPoints || []).filter(Boolean).slice(0, 3)

  return (
    <div
      className={`rounded-none border p-5 transition-all duration-200 ${TONE_STYLES[tone]}`}
    >
      <div className="flex items-start gap-4">
        <div className="mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-none border border-current/10 bg-background/80">
          <Icon className="h-5 w-5 text-cta" />
        </div>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                {normalizedEyebrow}
              </p>
              <p className="mt-1 text-base font-bold text-foreground break-words">
                {normalizedTitle}
              </p>
            </div>
            {metric !== null ? (
              <div className="min-w-[72px] border border-border bg-background/90 px-2.5 py-2 text-right shadow-sm">
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  {scoreLabel || 'Signal'}
                </p>
                <p className="mt-1 text-lg font-bold text-foreground">{metric}%</p>
              </div>
            ) : null}
          </div>

          {description ? (
            <p className="text-sm leading-relaxed text-muted-foreground break-words">
              {description}
            </p>
          ) : null}

          {visiblePoints.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {visiblePoints.map(point => (
                <span
                  key={point}
                  className="inline-flex items-center gap-1 border border-border bg-background/75 px-2.5 py-1 text-[11px] font-medium text-foreground"
                >
                  <ArrowUpRight className="h-3 w-3 text-muted-foreground" />
                  <span className="break-words">{point}</span>
                </span>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export function InsightCard(props: InsightCardProps) {
  const reduceMotion = Boolean(useReducedMotion())

  if (reduceMotion) {
    return <InsightCardBody {...props} />
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{
        delay: (props.index || 0) * 0.08,
        duration: 0.38,
        ease: 'easeOut',
      }}
    >
      <InsightCardBody {...props} />
    </motion.div>
  )
}

interface InsightsSectionProps {
  angles: string[]
}

export function InsightsSection({ angles }: InsightsSectionProps) {
  const { t } = useTranslation()
  if (angles.length === 0) return null

  return (
    <div>
      <div className="mb-5 flex items-center gap-2">
        <Lightbulb className="h-6 w-6 text-cta" />
        <div>
          <h2 className="text-xl font-bold font-heading text-foreground">
            {t('report.insight.title')}
          </h2>
          <p className="text-sm text-muted-foreground">
            Recommended execution angles once the build decision is positive enough.
          </p>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {angles.map((angle, index) => (
          <InsightCard
            key={`${angle}-${index}`}
            angle={angle}
            index={index}
            eyebrow="Differentiation angle"
            description="Use this as a practical wedge, not a generic product promise."
            tone="default"
          />
        ))}
      </div>
    </div>
  )
}
