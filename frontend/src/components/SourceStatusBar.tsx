import { Check, X, AlertTriangle, Clock } from 'lucide-react'
import type { SourceResult } from '../types/research'

const statusConfig: Record<string, { icon: typeof Check; color: string; bg: string }> = {
  ok: { icon: Check, color: 'text-cta', bg: 'bg-cta/10' },
  failed: { icon: X, color: 'text-danger', bg: 'bg-danger/10' },
  timeout: { icon: Clock, color: 'text-warning', bg: 'bg-warning/10' },
  degraded: { icon: AlertTriangle, color: 'text-warning', bg: 'bg-warning/10' },
  cached: { icon: Check, color: 'text-blue-400', bg: 'bg-blue-400/10' },
}

const platformLabels: Record<string, string> = {
  github: 'GitHub',
  tavily: 'Web Search',
  hackernews: 'Hacker News',
}

interface SourceStatusBarProps {
  sources: SourceResult[]
}

export function SourceStatusBar({ sources }: SourceStatusBarProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {sources.map(sr => {
        const cfg = statusConfig[sr.status] || statusConfig.failed
        const Icon = cfg.icon
        return (
          <div
            key={sr.platform}
            className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg ${cfg.bg} ${cfg.color} text-xs font-medium`}
          >
            <Icon className="w-3.5 h-3.5" />
            <span>{platformLabels[sr.platform] || sr.platform}</span>
            {sr.status === 'ok' && <span className="text-text-dim">({sr.raw_count})</span>}
            {sr.error_msg && <span className="text-text-dim truncate max-w-[120px]">{sr.error_msg}</span>}
          </div>
        )
      })}
    </div>
  )
}
