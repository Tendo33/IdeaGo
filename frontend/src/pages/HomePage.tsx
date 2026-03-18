import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SearchBox } from '../components/SearchBox'
import { isRequestAbortError, listReports, startAnalysis } from '../api/client'
import { AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ReportListItem } from '../types/research'

const MIN_QUERY_LENGTH = 5
const MAX_QUERY_LENGTH = 1000

export function HomePage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recentReports, setRecentReports] = useState<ReportListItem[]>([])
  const [recentReportsError, setRecentReportsError] = useState<string | null>(null)
  const isSubmittingRef = useRef(false)

  useEffect(() => {
    const controller = new AbortController()
    listReports({ limit: 5, offset: 0, signal: controller.signal })
      .then(reports => {
        setRecentReports(reports)
        setRecentReportsError(null)
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        setRecentReportsError(t('home.errorLoadRecent'))
      })
    return () => controller.abort()
  }, [t])

  const handleSubmit = async (query: string) => {
    const normalizedQuery = query.trim()
    if (
      isSubmittingRef.current ||
      normalizedQuery.length < MIN_QUERY_LENGTH ||
      normalizedQuery.length > MAX_QUERY_LENGTH
    ) {
      return
    }

    isSubmittingRef.current = true
    setIsLoading(true)
    setError(null)
    try {
      const { report_id } = await startAnalysis(normalizedQuery)
      navigate(`/reports/${report_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : t('home.errorStartAnalysis'))
    } finally {
      isSubmittingRef.current = false
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen px-4 pb-12 pt-10 sm:pt-14">
      <div className="app-shell grid items-start gap-12 lg:grid-cols-[1fr_340px]">
        <section className="py-12 lg:py-20 text-left animate-fade-in pr-0 lg:pr-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 mb-6 rounded-full border border-primary text-xs font-bold text-primary tracking-widest uppercase">
            {t('app.title')} {t('app.titleHighlight')}
          </div>
          <h1 className="mb-6 text-5xl font-black tracking-tighter text-foreground sm:text-7xl leading-[1.1]">
            {t('app.title')}
            <span className="block text-primary">{t('app.titleHighlight')}</span>
          </h1>
          <p className="mb-12 max-w-xl text-lg font-medium leading-relaxed text-muted-foreground sm:text-xl">
            {t('home.description')}
          </p>

          <SearchBox onSubmit={handleSubmit} isLoading={isLoading} />

          <div className="mt-8 flex flex-wrap gap-3">
            {[0, 1, 2, 3].map(index => {
              const prompt = t(`home.prompt${index}`)
              return (
                <button
                  key={prompt}
                  onClick={() => handleSubmit(prompt)}
                  disabled={isLoading}
                  className="px-4 py-2 text-sm font-medium rounded-none border-b-2 border-transparent text-muted-foreground hover:text-foreground hover:border-primary transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-40"
                >
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

        <aside className="surface-card p-6 sm:p-8 animate-fade-in [animation-delay:120ms] border-t-4 border-t-primary rounded-none sm:rounded-xl">
          <h2 className="mb-6 text-sm font-black uppercase tracking-[0.2em] text-foreground border-b border-border pb-4">
            {t('home.recentResearch')}
          </h2>

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
                  className="group flex w-full cursor-pointer items-start justify-between py-4 text-left hover:bg-muted/30 transition-colors border-b border-border/50 last:border-0"
                >
                  <div className="min-w-0 flex-1 pr-4">
                    <p className="text-base font-bold text-foreground leading-tight group-hover:text-primary transition-colors line-clamp-2">{report.query}</p>
                    <div className="mt-2 flex items-center gap-4">
                      <span className="text-xs font-mono text-muted-foreground uppercase tracking-wider">
                        {new Date(report.created_at).toLocaleDateString()}
                      </span>
                      <span className="text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded">
                        {report.competitor_count} {t('home.competitors')}
                      </span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {!recentReportsError && recentReports.length === 0 && (
            <div className="py-8 text-left">
              <p className="text-sm font-medium text-muted-foreground">
                {t('history.emptyState')}
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
