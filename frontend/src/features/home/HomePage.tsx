import { useEffect, useState, memo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { SearchBox } from './components/SearchBox'
import { isRequestAbortError, listReports } from '../../lib/api/client'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import type { ReportListItem } from '../../lib/types/research'

const MIN_QUERY_LENGTH = 5
const MAX_QUERY_LENGTH = 1000

interface RecentReportItemProps {
  report: ReportListItem;
  idx: number;
  onNavigate: (id: string) => void;
  t: (key: string) => string;
}

const RecentReportItem = memo(function RecentReportItem({ report, idx, onNavigate, t }: RecentReportItemProps) {
  return (
    <button
      onClick={() => onNavigate(report.id)}
      className="group block w-full text-left bg-background border-2 border-border p-4 shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] focus-visible:translate-x-[2px] focus-visible:translate-y-[2px] focus-visible:shadow-[2px_2px_0px_0px_var(--border)] transition-all duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
    >
      <div className="flex gap-4 items-start">
        <span className="text-3xl font-black text-muted-foreground/30 leading-none">0{idx + 1}</span>
        <div>
          <p className="text-lg font-bold text-foreground leading-tight group-hover:text-primary transition-colors line-clamp-2 wrap" title={report.query}>
            {report.query}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2 sm:gap-3">
            <Badge variant="secondary" className="text-[10px] sm:text-xs">
              {new Date(report.created_at).toLocaleDateString()}
            </Badge>
            <Badge variant="primary" className="text-[10px] sm:text-xs">
              {report.competitor_count} {t('home.competitors')}
            </Badge>
          </div>
        </div>
      </div>
    </button>
  )
})

export function HomePage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [recentReports, setRecentReports] = useState<ReportListItem[]>([])
  const [recentReportsError, setRecentReportsError] = useState<string | null>(null)

  const handleNavigate = useCallback((id: string) => {
    navigate(`/reports/${id}`)
  }, [navigate])

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleSubmit = useCallback((query: string) => {
    const normalizedQuery = query.trim()
    if (
      normalizedQuery.length < MIN_QUERY_LENGTH ||
      normalizedQuery.length > MAX_QUERY_LENGTH
    ) {
      return
    }
    navigate('/reports/new', { state: { query: normalizedQuery } })
  }, [navigate])

  return (
    <div className="min-h-screen px-4 pb-16 pt-12 sm:pt-20 bg-background text-foreground selection:bg-primary selection:text-primary-foreground">
      <div className="app-shell grid items-start gap-16 lg:grid-cols-[1fr_400px]">

        {/* Main Content Section */}
        <section className="py-12 lg:py-16 text-left animate-fade-in">
          <h1 className="mb-8 font-heading uppercase tracking-tighter leading-[0.9] text-6xl sm:text-8xl md:text-[7rem] break-words">
            {t('app.title')}
            <br />
            <span className="text-primary">{t('app.titleHighlight')}</span>
          </h1>

          <p className="mb-12 max-w-2xl text-xl md:text-2xl font-bold leading-snug text-muted-foreground border-l-4 border-primary pl-6">
            {t('home.description')}
          </p>

          <div className="bg-card border-2 border-border shadow-[6px_6px_0px_0px_var(--border)] p-6 md:p-8">
            <SearchBox onSubmit={handleSubmit} />

            <div className="mt-8">
              <h3 className="text-sm font-bold uppercase tracking-widest text-muted-foreground mb-4">{t('home.quickPrompts', { defaultValue: 'Quick Prompts' })}</h3>
              <div className="flex flex-wrap gap-2">
                {[0, 1, 2, 3].map(index => {
                  const prompt = t(`home.prompt${index}`)
                  return (
                    <Button
                      key={prompt}
                      variant="secondary"
                      onClick={() => handleSubmit(prompt)}
                      className="flex-1 min-w-[200px] text-left justify-start"
                      title={prompt}
                    >
                      <span className="truncate">{prompt}</span>
                    </Button>
                  )
                })}
              </div>
            </div>

          </div>
        </section>

        {/* Sidebar - Recent Research */}
        <aside className="lg:mt-32 card bg-secondary text-secondary-foreground animate-fade-in [animation-delay:150ms]">
          <h2 className="mb-8 text-2xl font-black uppercase tracking-tight border-b-4 border-border pb-4">
            {t('home.recentResearch')}
          </h2>

          {recentReportsError && (
            <Alert variant="warning" className="mb-6">
              <span className="font-bold">{recentReportsError}</span>
            </Alert>
          )}

          {recentReports.length > 0 && (
            <div className="space-y-6">
              {recentReports.map((report, idx) => (
                <RecentReportItem
                  key={report.id}
                  report={report}
                  idx={idx}
                  onNavigate={handleNavigate}
                  t={t}
                />
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
