import { Download, ArrowRight, Lightbulb } from 'lucide-react'
import type { ResearchReport } from '../types/research'
import { getExportUrl } from '../api/client'

interface ReportSummaryProps {
  report: ResearchReport
}

function getRecommendationStyle(goNoGo: string) {
  const lower = goNoGo.toLowerCase()
  if (lower.startsWith('no-go') || lower.startsWith('no go'))
    return { bg: 'bg-danger/10 border-danger/30', text: 'text-danger' }
  if (lower.includes('caution'))
    return { bg: 'bg-warning/10 border-warning/30', text: 'text-warning' }
  return { bg: 'bg-cta/10 border-cta/30', text: 'text-cta' }
}

export function ReportSummary({ report }: ReportSummaryProps) {
  const recStyle = getRecommendationStyle(report.go_no_go)

  return (
    <div className="space-y-6">
      {report.go_no_go && (
        <div className={`rounded-xl border p-5 ${recStyle.bg}`}>
          <h2 className={`text-lg font-semibold font-[family-name:var(--font-heading)] mb-2 ${recStyle.text}`}>
            Recommendation
          </h2>
          <p className="text-sm text-text leading-relaxed">{report.go_no_go}</p>
        </div>
      )}

      {report.market_summary && (
        <div>
          <h2 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text mb-3">
            Market Overview
          </h2>
          <p className="text-sm text-text-muted leading-relaxed whitespace-pre-line">{report.market_summary}</p>
        </div>
      )}

      {report.differentiation_angles.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text mb-3 flex items-center gap-2">
            <Lightbulb className="w-5 h-5 text-cta" />
            Differentiation Opportunities
          </h2>
          <ul className="space-y-2">
            {report.differentiation_angles.map((angle, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-muted">
                <ArrowRight className="w-4 h-4 text-cta shrink-0 mt-0.5" />
                <span>{angle}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <a
        href={getExportUrl(report.id)}
        download
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary text-text text-sm font-medium cursor-pointer transition-colors duration-200 hover:bg-bg-card-hover focus:outline-none focus:ring-2 focus:ring-cta/30"
      >
        <Download className="w-4 h-4" />
        Export as Markdown
      </a>
    </div>
  )
}
