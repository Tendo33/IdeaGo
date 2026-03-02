import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SearchBox } from '../components/SearchBox'
import { isRequestAbortError, listReports, startAnalysis } from '../api/client'
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
    const controller = new AbortController()
    listReports({ signal: controller.signal })
      .then(reports => {
        setRecentReports(reports.slice(0, 5))
        setRecentReportsError(null)
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        setRecentReportsError(t('home.errorLoadRecent'))
      })
    return () => controller.abort()
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
    <div className="min-h-screen px-4 pb-12 pt-10 sm:pt-14">
      <div className="app-shell grid items-start gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(280px,1fr)] lg:gap-8">
        <section className="panel-soft px-6 py-8 text-center sm:px-10 sm:py-10 lg:text-left animate-fade-in">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            {t('app.title')}
            {t('app.titleHighlight')}
          </div>
          <h1 className="mb-4 text-4xl font-bold tracking-tight text-text sm:text-5xl">
            {t('app.title')}
            <span className="text-primary">{t('app.titleHighlight')}</span>
          </h1>
          <p className="mx-auto mb-8 max-w-2xl text-base leading-relaxed text-text-muted sm:text-lg lg:mx-0">
            {t('home.description')}
          </p>

          <SearchBox onSubmit={handleSubmit} isLoading={isLoading} />

          <div className="mt-6 flex flex-wrap justify-center gap-2 lg:justify-start">
            {[0, 1, 2, 3].map(index => {
              const prompt = t(`home.prompt${index}`)
              return (
                <button
                  key={prompt}
                  onClick={() => handleSubmit(prompt)}
                  disabled={isLoading}
                  className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-border bg-bg-card px-3 py-1.5 text-xs text-text-muted transition-all duration-200 hover:border-primary/30 hover:bg-bg-card-hover hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
                >
                  <Sparkles className="h-3 w-3" />
                  {prompt}
                </button>
              )
            })}
          </div>

          {error && (
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-danger/20 bg-danger/10 px-4 py-3 text-left">
              <AlertCircle className="h-4 w-4 shrink-0 text-danger" />
              <p className="text-sm text-danger">{error}</p>
            </div>
          )}
        </section>

        <aside className="surface-card p-4 sm:p-6 animate-fade-in [animation-delay:120ms]">
          <h2 className="mb-1 text-xs font-semibold uppercase tracking-[0.16em] text-text-dim">
            {t('home.recentResearch')}
          </h2>
          <p className="mb-4 text-sm text-text-muted">{t('search.example')}</p>

          {recentReportsError && (
            <p className="mb-3 rounded-lg border border-warning/25 bg-warning/10 px-3 py-2 text-xs text-warning">
              {recentReportsError}
            </p>
          )}

          {recentReports.length > 0 && (
            <div className="space-y-2.5">
              {recentReports.map(report => (
                <button
                  key={report.id}
                  onClick={() => navigate(`/reports/${report.id}`)}
                  className="group flex w-full cursor-pointer items-center justify-between rounded-xl border border-border bg-bg-card px-4 py-3 text-left transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-bg-card-hover focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-text">{report.query}</p>
                    <div className="mt-1 flex items-center gap-3">
                      <span className="inline-flex items-center gap-1 text-xs text-text-dim">
                        <Clock className="h-3 w-3" />
                        {new Date(report.created_at).toLocaleDateString()}
                      </span>
                      <span className="text-xs font-medium text-primary">
                        {report.competitor_count} {t('home.competitors')}
                      </span>
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 shrink-0 text-text-dim transition-colors duration-200 group-hover:text-primary" />
                </button>
              ))}
            </div>
          )}

          {!recentReportsError && recentReports.length === 0 && (
            <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-text-dim">
              {t('history.emptyState')}
            </p>
          )}
        </aside>
      </div>
    </div>
  )
}
