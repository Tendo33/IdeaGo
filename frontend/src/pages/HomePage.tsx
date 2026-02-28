import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SearchBox } from '../components/SearchBox'
import { startAnalysis, listReports } from '../api/client'
import { Clock, ChevronRight, AlertCircle, Sparkles } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ReportListItem } from '../types/research'


export function HomePage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recentReports, setRecentReports] = useState<ReportListItem[]>([])
  const [recentReportsError, setRecentReportsError] = useState<string | null>(null)

  useEffect(() => {
    listReports()
      .then(reports => {
        setRecentReports(reports.slice(0, 5))
        setRecentReportsError(null)
      })
      .catch(() => {
        setRecentReportsError(t('home.errorLoadRecent'))
      })
  }, [t])

  const handleSubmit = async (query: string) => {
    setIsLoading(true)
    setError(null)
    try {
      const { report_id } = await startAnalysis(query)
      navigate(`/reports/${report_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('home.errorStartAnalysis'))
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-2xl mx-auto text-center -mt-20">
        <h1 className="text-5xl font-bold font-heading mb-4 tracking-tight">
          {t('app.title')}<span className="text-cta">{t('app.titleHighlight')}</span>
        </h1>
        <p className="text-lg text-text-muted mb-10 max-w-md mx-auto">
          {t('home.description')}
        </p>
        <SearchBox onSubmit={handleSubmit} isLoading={isLoading} />

        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {[0, 1, 2, 3].map(index => {
            const prompt = t(`home.prompt${index}`)
            return (
              <button
                key={prompt}
                onClick={() => handleSubmit(prompt)}
                disabled={isLoading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs text-text-muted rounded-full border border-border bg-bg-card cursor-pointer transition-all duration-200 hover:border-cta/40 hover:text-cta hover:bg-bg-card-hover disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Sparkles className="w-3 h-3" />
                {prompt}
              </button>
            )
          })}
        </div>

        {error && (
          <div className="mt-4 flex items-center gap-2 px-4 py-3 rounded-lg bg-danger/10 border border-danger/30 text-left">
            <AlertCircle className="w-4 h-4 text-danger shrink-0" />
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        {recentReportsError && (
          <p className="mt-3 text-xs text-text-dim">{recentReportsError}</p>
        )}

        {recentReports.length > 0 && (
          <div className="mt-16 w-full">
            <h2 className="text-sm font-medium text-text-dim mb-4 uppercase tracking-wider">{t('home.recentResearch')}</h2>
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
                      <span className="text-xs text-cta">{report.competitor_count} {t('home.competitors')}</span>
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
