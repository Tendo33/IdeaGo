import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { Check, X, AlertTriangle, Clock, ChevronDown, ChevronUp, Users, Target, TrendingUp, Lightbulb } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import type { ResearchReport, RecommendationType, SourceResult } from '@/lib/types/research'
import { normalizeSourceErrorMessage } from '@/lib/utils/sourceErrorMessage'

interface HeroPanelProps {
  report: ResearchReport
}

function getVerdictConfig(type: RecommendationType, t: TFunction) {
  const baseConfigs = {
    go: { glow: 'shadow-[6px_6px_0px_0px_var(--success)]', bg: 'bg-success/10', text: 'text-success', ring: 'border-success' },
    caution: { glow: 'shadow-[6px_6px_0px_0px_var(--warning)]', bg: 'bg-warning/10', text: 'text-warning', ring: 'border-warning' },
    no_go: { glow: 'shadow-[6px_6px_0px_0px_var(--destructive)]', bg: 'bg-destructive/10', text: 'text-destructive', ring: 'border-destructive' }
  }

  const config = baseConfigs[type] || baseConfigs.go

  return {
    ...config,
    label: type === 'go' ? t('report.hero.verdict.go') : type === 'caution' ? t('report.hero.verdict.caution') : t('report.hero.verdict.noGo')
  }
}

const SOURCE_STATUS_ICON: Record<string, typeof Check> = {
  ok: Check,
  failed: X,
  timeout: Clock,
  degraded: AlertTriangle,
  cached: Check,
}

const SOURCE_STATUS_COLOR: Record<string, string> = {
  ok: 'text-cta',
  failed: 'text-danger',
  timeout: 'text-warning',
  degraded: 'text-warning',
  cached: 'text-chart-2',
}

const PLATFORM_LABELS: Record<string, string> = {
  github: 'GitHub',
  tavily: 'Web',
  hackernews: 'HN',
  appstore: 'App Store',
}

function SourceStatusInline({ sources }: { sources: SourceResult[] }) {
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs">
      {sources.map(sr => {
        const Icon = SOURCE_STATUS_ICON[sr.status] ?? X
        const color = SOURCE_STATUS_COLOR[sr.status] ?? 'text-danger'
        return (
          <span key={sr.platform} className={`inline-flex items-center gap-1.5 ${color}`}>
            <Icon className="w-3 h-3" />
            <span>{PLATFORM_LABELS[sr.platform] ?? sr.platform}</span>
            {sr.status === 'ok' && (
              <span className="text-text-dim">
                {sr.raw_count} ({(sr.duration_ms / 1000).toFixed(1)}s)
              </span>
            )}
            {sr.status !== 'ok' && sr.error_msg && (
              <span className="text-text-dim truncate max-w-24">
                {normalizeSourceErrorMessage(sr.status, sr.error_msg)}
              </span>
            )}
          </span>
        )
      })}
    </div>
  )
}

function StatCard({
  value,
  label,
  icon: Icon,
  index,
  reduceMotion = false,
}: {
  value: string | number
  label: string
  icon: typeof Users
  index: number
  reduceMotion?: boolean
}) {
  const content = (
    <>
      <div className="flex items-center gap-2.5 mb-2.5">
        <Icon className="w-5 h-5 text-text-dim" />
        <span className="text-sm text-text-dim font-medium">{label}</span>
      </div>
      <p className="text-4xl font-bold font-heading text-text">{value}</p>
    </>
  )

  if (reduceMotion) {
    return (
      <div className="rounded-none bg-card border-2 border-border p-6 shadow-[4px_4px_0px_0px_var(--border)]">
        {content}
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 + index * 0.08, duration: 0.4, ease: 'easeOut' }}
      className="rounded-none bg-card border-2 border-border p-6 transition-all duration-150 shadow-[4px_4px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] hover:bg-muted"
    >
      {content}
    </motion.div>
  )
}

export function HeroPanel({ report }: HeroPanelProps) {
  const { t } = useTranslation()
  const [expanded, setExpanded] = useState(false)
  const reduceMotion = Boolean(useReducedMotion())
  const verdict = getVerdictConfig(report.recommendation_type, t)

  const competitorCount = report.competitors.length
  const avgRelevance = competitorCount > 0
    ? Math.round((report.competitors.reduce((s, c) => s + c.relevance_score, 0) / competitorCount) * 100)
    : 0
  const intensity = competitorCount > 0
    ? Math.min(10, Math.round((report.competitors.filter(c => c.relevance_score >= 0.7).length / competitorCount) * 10))
    : 0
  const angleCount = report.differentiation_angles.length

  return (
    <section id="section-summary" className="grid grid-cols-1 lg:grid-cols-5 gap-5">
      {/* Verdict Card — left 3/5 */}
      <div className={`lg:col-span-3 rounded-none border-2 border-border ${verdict.bg} p-8 sm:p-10 ${verdict.glow}`}>
        <div className="flex items-start gap-5 mb-5">
          <div className={`w-16 h-16 rounded-none ${verdict.bg} border-2 ${verdict.ring} flex items-center justify-center shrink-0 shadow-[4px_4px_0px_0px_currentColor] ${verdict.text}`}>
            <span className="text-3xl font-black font-heading">
              {report.recommendation_type === 'go' ? '✓' : report.recommendation_type === 'no_go' ? '✗' : '!'}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <h2 className={`text-2xl font-bold font-heading ${verdict.text} mb-2`}>
              {verdict.label}
            </h2>
            {report.go_no_go && (
              <div className="relative">
                <p className={`text-base text-text leading-relaxed break-words ${!expanded ? 'line-clamp-3' : ''}`}>
                  {report.go_no_go}
                </p>
                {report.go_no_go.length > 200 && (
                  <button
                    onClick={() => setExpanded(e => !e)}
                    className="mt-1 inline-flex items-center gap-1 text-xs text-text-muted hover:text-cta transition-colors cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none rounded-none px-1"
                  >
                    {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {expanded ? t('report.hero.showLess') : t('report.hero.readMore')}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {report.source_results.length > 0 && (
          <div className="pt-4 border-t-2 border-border">
            <SourceStatusInline sources={report.source_results} />
          </div>
        )}
      </div>

      {/* Stats Grid — right 2/5 */}
      <div className="lg:col-span-2 grid grid-cols-2 gap-3">
        <StatCard value={competitorCount} label={t('report.hero.stats.competitors')} icon={Users} index={0} reduceMotion={reduceMotion} />
        <StatCard value={`${avgRelevance}%`} label={t('report.hero.stats.avgRelevance')} icon={Target} index={1} reduceMotion={reduceMotion} />
        <StatCard value={`${intensity}/10`} label={t('report.hero.stats.competition')} icon={TrendingUp} index={2} reduceMotion={reduceMotion} />
        <StatCard value={angleCount} label={t('report.hero.stats.opportunities')} icon={Lightbulb} index={3} reduceMotion={reduceMotion} />
      </div>
    </section>
  )
}
