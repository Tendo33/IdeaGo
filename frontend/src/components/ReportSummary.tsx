import { useState } from 'react'
import { Download, ArrowRight, Lightbulb, Link2, Check, Printer } from 'lucide-react'
import type { ResearchReport, RecommendationType } from '../types/research'
import { getExportUrl } from '../api/client'

interface ReportSummaryProps {
  report: ResearchReport
}

const RECOMMENDATION_STYLES: Record<RecommendationType, { bg: string; text: string }> = {
  no_go: { bg: 'bg-danger/10 border-danger/30', text: 'text-danger' },
  caution: { bg: 'bg-warning/10 border-warning/30', text: 'text-warning' },
  go: { bg: 'bg-cta/10 border-cta/30', text: 'text-cta' },
}

export function ReportSummary({ report }: ReportSummaryProps) {
  const [copied, setCopied] = useState(false)
  const recStyle = RECOMMENDATION_STYLES[report.recommendation_type] ?? RECOMMENDATION_STYLES.go

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

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

      <div className="flex flex-wrap gap-3">
        <a
          href={getExportUrl(report.id)}
          download
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary text-text text-sm font-medium cursor-pointer transition-colors duration-200 hover:bg-bg-card-hover focus:outline-none focus:ring-2 focus:ring-cta/30"
        >
          <Download className="w-4 h-4" />
          Export as Markdown
        </a>
        <button
          onClick={handleCopyLink}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary text-text text-sm font-medium cursor-pointer transition-colors duration-200 hover:bg-bg-card-hover focus:outline-none focus:ring-2 focus:ring-cta/30"
        >
          {copied ? <Check className="w-4 h-4 text-cta" /> : <Link2 className="w-4 h-4" />}
          {copied ? 'Copied!' : 'Copy Link'}
        </button>
        <button
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary text-text text-sm font-medium cursor-pointer transition-colors duration-200 hover:bg-bg-card-hover focus:outline-none focus:ring-2 focus:ring-cta/30 no-print"
        >
          <Printer className="w-4 h-4" />
          Export as PDF
        </button>
      </div>
    </div>
  )
}
