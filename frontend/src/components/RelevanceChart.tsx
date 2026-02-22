import type { Competitor } from '../types/research'

interface RelevanceChartProps {
  competitors: Competitor[]
}

export function RelevanceChart({ competitors }: RelevanceChartProps) {
  if (competitors.length === 0) return null

  const high = competitors.filter(c => c.relevance_score >= 0.7).length
  const medium = competitors.filter(c => c.relevance_score >= 0.4 && c.relevance_score < 0.7).length
  const low = competitors.filter(c => c.relevance_score < 0.4).length
  const total = competitors.length

  const avgScore = Math.round(
    (competitors.reduce((sum, c) => sum + c.relevance_score, 0) / total) * 100
  )

  const bars = [
    { label: 'High (70-100%)', count: high, color: 'bg-cta', textColor: 'text-cta' },
    { label: 'Medium (40-69%)', count: medium, color: 'bg-warning', textColor: 'text-warning' },
    { label: 'Low (0-39%)', count: low, color: 'bg-text-dim', textColor: 'text-text-dim' },
  ]

  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold font-[family-name:var(--font-heading)] text-text">
          Relevance Distribution
        </h3>
        <span className="text-xs text-text-muted">
          Avg. score: <span className="font-semibold text-cta">{avgScore}%</span>
        </span>
      </div>
      <div className="space-y-3">
        {bars.map(bar => (
          <div key={bar.label}>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className={bar.textColor}>{bar.label}</span>
              <span className="text-text-muted">{bar.count}</span>
            </div>
            <div className="h-2 rounded-full bg-border overflow-hidden">
              <div
                className={`h-full rounded-full ${bar.color} transition-all duration-500`}
                style={{ width: total > 0 ? `${(bar.count / total) * 100}%` : '0%' }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
