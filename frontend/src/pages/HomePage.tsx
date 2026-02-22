import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SearchBox } from '../components/SearchBox'
import { startAnalysis, listReports } from '../api/client'
import { Clock, ChevronRight, AlertCircle, Sparkles } from 'lucide-react'
import type { ReportListItem } from '../types/research'

const EXAMPLE_PROMPTS = [
  'An AI tool that summarizes meeting notes automatically',
  'A marketplace for local organic food delivery',
  'A browser extension that converts web pages to Markdown',
  'A developer tool for real-time API monitoring',
]

export function HomePage() {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recentReports, setRecentReports] = useState<ReportListItem[]>([])

  useEffect(() => {
    listReports()
      .then(reports => setRecentReports(reports.slice(0, 5)))
      .catch(() => { /* Recent reports are non-critical; fail silently */ })
  }, [])

  const handleSubmit = async (query: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const { report_id } = await startAnalysis(query)
      navigate(`/reports/${report_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start analysis. Please try again.')
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-2xl mx-auto text-center -mt-20">
        <h1 className="text-5xl font-bold font-[family-name:var(--font-heading)] mb-4 tracking-tight">
          Idea<span className="text-cta">Go</span>
        </h1>
        <p className="text-lg text-text-muted mb-10 max-w-md mx-auto">
          Validate your startup idea with real competitor data from GitHub, web, and Hacker News.
        </p>
        <SearchBox onSubmit={handleSubmit} isLoading={isLoading} />

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {EXAMPLE_PROMPTS.map(prompt => (
            <button
              key={prompt}
              onClick={() => handleSubmit(prompt)}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-muted rounded-full border border-border bg-bg-card cursor-pointer transition-all duration-200 hover:border-cta/40 hover:text-cta hover:bg-bg-card-hover disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Sparkles className="w-3 h-3" />
              {prompt}
            </button>
          ))}
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 px-4 py-3 rounded-lg bg-danger/10 border border-danger/30 text-left">
            <AlertCircle className="w-4 h-4 text-danger shrink-0" />
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        {recentReports.length > 0 && (
          <div className="mt-16 w-full">
            <h2 className="text-sm font-medium text-text-dim mb-4 uppercase tracking-wider">Recent Research</h2>
            <div className="space-y-2">
              {recentReports.map(report => (
                <button
                  key={report.id}
                  onClick={() => navigate(`/reports/${report.id}`)}
                  className="w-full flex items-center justify-between px-4 py-3 rounded-lg bg-bg-card border border-border text-left cursor-pointer transition-all duration-200 hover:border-cta/30 hover:bg-bg-card-hover group focus:outline-none focus:ring-2 focus:ring-cta/30"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-text truncate">{report.query}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className="text-xs text-text-dim flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {new Date(report.created_at).toLocaleDateString()}
                      </span>
                      <span className="text-xs text-cta">{report.competitor_count} competitors</span>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-text-dim group-hover:text-cta transition-colors duration-200 shrink-0" />
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
