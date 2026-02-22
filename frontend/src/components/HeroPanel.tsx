import { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, X, AlertTriangle, Clock, ChevronDown, ChevronUp, Users, Target, TrendingUp, Lightbulb } from 'lucide-react'
import type { ResearchReport, RecommendationType, SourceResult } from '../types/research'

interface HeroPanelProps {
  report: ResearchReport
}

const VERDICT_CONFIG: Record<RecommendationType, { label: string; glow: string; bg: string; text: string; ring: string }> = {
  go: {
    label: 'GO',
    glow: 'shadow-[0_0_40px_rgba(34,197,94,0.3)]',
    bg: 'bg-cta/15',
    text: 'text-cta',
    ring: 'ring-cta/40',
  },
  caution: {
    label: 'CAUTION',
    glow: 'shadow-[0_0_40px_rgba(245,158,11,0.3)]',
    bg: 'bg-warning/15',
    text: 'text-warning',
    ring: 'ring-warning/40',
  },
  no_go: {
    label: 'NO-GO',
    glow: 'shadow-[0_0_40px_rgba(239,68,68,0.3)]',
    bg: 'bg-danger/15',
    text: 'text-danger',
    ring: 'ring-danger/40',
  },
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
  cached: 'text-blue-400',
}

const PLATFORM_LABELS: Record<string, string> = {
  github: 'GitHub',
  tavily: 'Web',
  hackernews: 'HN',
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
              <span className="text-text-dim truncate max-w-24">{sr.error_msg}</span>
            )}
          </span>
        )
      })}
    </div>
  )
}

function StatCard({ value, label, icon: Icon, index }: { value: string | number; label: string; icon: typeof Users; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 + index * 0.08, duration: 0.4, ease: 'easeOut' }}
      className="rounded-xl bg-bg-card border border-border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/20"
    >
      <div className="flex items-center gap-2 mb-1.5">
        <Icon className="w-4 h-4 text-text-dim" />
        <span className="text-xs text-text-dim">{label}</span>
      </div>
      <p className="text-3xl font-bold font-[family-name:var(--font-heading)] text-text">{value}</p>
    </motion.div>
  )
}

export function HeroPanel({ report }: HeroPanelProps) {
  const [expanded, setExpanded] = useState(false)
  const verdict = VERDICT_CONFIG[report.recommendation_type] ?? VERDICT_CONFIG.go

  const competitorCount = report.competitors.length
  const avgRelevance = competitorCount > 0
    ? Math.round((report.competitors.reduce((s, c) => s + c.relevance_score, 0) / competitorCount) * 100)
    : 0
  const intensity = competitorCount > 0
    ? Math.min(10, Math.round((report.competitors.filter(c => c.relevance_score >= 0.7).length / competitorCount) * 10))
    : 0
  const angleCount = report.differentiation_angles.length

  return (
    <section id="section-summary" className="grid grid-cols-1 lg:grid-cols-5 gap-4">
      {/* Verdict Card — left 3/5 */}
      <div className={`lg:col-span-3 rounded-xl border border-border ${verdict.bg} p-6 ${verdict.glow} animate-hero-glow`}>
        <div className="flex items-start gap-4 mb-4">
          <div className={`w-14 h-14 rounded-full ${verdict.bg} ring-2 ${verdict.ring} flex items-center justify-center shrink-0 animate-verdict-pulse`}>
            <span className={`text-lg font-bold font-[family-name:var(--font-heading)] ${verdict.text}`}>
              {verdict.label === 'GO' ? '✓' : verdict.label === 'NO-GO' ? '✗' : '!'}
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <h2 className={`text-xl font-bold font-[family-name:var(--font-heading)] ${verdict.text} mb-1`}>
              {verdict.label}
            </h2>
            {report.go_no_go && (
              <div className="relative">
                <p className={`text-sm text-text leading-relaxed ${!expanded ? 'line-clamp-3' : ''}`}>
                  {report.go_no_go}
                </p>
                {report.go_no_go.length > 200 && (
                  <button
                    onClick={() => setExpanded(e => !e)}
                    className="mt-1 inline-flex items-center gap-1 text-xs text-text-muted hover:text-cta transition-colors cursor-pointer"
                  >
                    {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {expanded ? 'Less' : 'Read more'}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {report.source_results.length > 0 && (
          <div className="pt-3 border-t border-white/10">
            <SourceStatusInline sources={report.source_results} />
          </div>
        )}
      </div>

      {/* Stats Grid — right 2/5 */}
      <div className="lg:col-span-2 grid grid-cols-2 gap-3">
        <StatCard value={competitorCount} label="Competitors" icon={Users} index={0} />
        <StatCard value={`${avgRelevance}%`} label="Avg. Relevance" icon={Target} index={1} />
        <StatCard value={`${intensity}/10`} label="Competition" icon={TrendingUp} index={2} />
        <StatCard value={angleCount} label="Opportunities" icon={Lightbulb} index={3} />
      </div>
    </section>
  )
}
