import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { SearchBox } from './components/SearchBox'
import { isRequestAbortError, listReports, startAnalysis } from '../../lib/api/client'
import { AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ReportListItem } from '../../lib/types/research'

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
    <div className="min-h-screen px-4 pb-16 pt-12 sm:pt-20 bg-background text-foreground selection:bg-primary selection:text-primary-foreground">
      <div className="app-shell grid items-start gap-16 lg:grid-cols-[1fr_400px]">

        {/* Main Content Section */}
        <section className="py-12 lg:py-16 text-left animate-fade-in">
          <div className="inline-block px-4 py-2 mb-8 border-2 border-border font-bold uppercase tracking-widest bg-primary text-primary-foreground shadow-[4px_4px_0px_0px_var(--border)]">
            {t('app.title')} {t('app.titleHighlight')}
          </div>

          <h1 className="mb-8 font-heading uppercase tracking-tighter leading-[0.9] text-6xl sm:text-8xl md:text-[7rem] break-words">
            {t('app.title')}
            <br />
            <span className="text-primary">{t('app.titleHighlight')}</span>
          </h1>

          <p className="mb-12 max-w-2xl text-xl md:text-2xl font-bold leading-snug text-muted-foreground border-l-4 border-primary pl-6">
            {t('home.description')}
          </p>

          <div className="bg-card border-2 border-border shadow-[6px_6px_0px_0px_var(--border)] p-6 md:p-8">
            <SearchBox onSubmit={handleSubmit} isLoading={isLoading} />

            <div className="mt-8">
              <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-4">Quick Prompts</h3>
              <div className="flex flex-wrap gap-3">
                {[0, 1, 2, 3].map(index => {
                  const prompt = t(`home.prompt${index}`)
                  return (
                    <button
                      key={prompt}
                      onClick={() => handleSubmit(prompt)}
                      disabled={isLoading}
                      className="px-4 py-2 text-sm font-bold uppercase tracking-wider border-2 border-border bg-background hover:bg-primary hover:text-primary-foreground hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] transition-all duration-150 disabled:opacity-50 disabled:cursor-not-allowed shadow-[4px_4px_0px_0px_var(--border)]"
                    >
                      {prompt}
                    </button>
                  )
                })}
              </div>
            </div>

            {error && (
              <div className="mt-6 flex items-start gap-3 border-2 border-destructive bg-destructive/10 p-4 shadow-[4px_4px_0px_0px_var(--destructive)]">
                <AlertCircle className="h-6 w-6 shrink-0 text-destructive mt-0.5" />
                <p className="text-sm font-bold text-destructive">{error}</p>
              </div>
            )}
          </div>
        </section>

        {/* Sidebar - Recent Research */}
        <aside className="lg:mt-32 card bg-secondary text-secondary-foreground animate-fade-in [animation-delay:150ms]">
          <h2 className="mb-8 text-2xl font-black uppercase tracking-tight border-b-4 border-border pb-4">
            {t('home.recentResearch')}
          </h2>

          {recentReportsError && (
            <div className="mb-6 border-2 border-warning bg-warning/20 p-3 shadow-[4px_4px_0px_0px_var(--warning)]">
              <p className="text-sm font-bold text-warning">{recentReportsError}</p>
            </div>
          )}

          {recentReports.length > 0 && (
            <div className="space-y-6">
              {recentReports.map((report, idx) => (
                <button
                  key={report.id}
                  onClick={() => navigate(`/reports/${report.id}`)}
                  className="group block w-full text-left bg-background border-2 border-border p-4 shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] transition-all duration-150 cursor-pointer"
                >
                  <div className="flex gap-4 items-start">
                    <span className="text-3xl font-black text-muted-foreground/30 leading-none">0{idx + 1}</span>
                    <div>
                      <p className="text-lg font-bold text-foreground leading-tight group-hover:text-primary transition-colors line-clamp-2">
                        {report.query}
                      </p>
                      <div className="mt-3 flex items-center gap-3">
                        <span className="text-xs font-bold text-muted-foreground uppercase tracking-widest border border-border px-2 py-1">
                          {new Date(report.created_at).toLocaleDateString()}
                        </span>
                        <span className="text-xs font-black text-primary-foreground bg-primary border-2 border-border px-2 py-1 shadow-[2px_2px_0px_0px_var(--border)]">
                          {report.competitor_count} {t('home.competitors')}
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}

          {!recentReportsError && recentReports.length === 0 && (
            <div className="py-12 px-6 text-center border-2 border-dashed border-border">
              <p className="text-sm font-bold uppercase tracking-widest text-muted-foreground">
                {t('history.emptyState')}
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
