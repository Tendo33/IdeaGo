import { useEffect, useState, memo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { SearchBox } from './components/SearchBox'
import { isRequestAbortError, listReports } from '../../lib/api/client'
import { useTranslation } from 'react-i18next'
import { Alert } from '../../components/ui/Alert'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import type { ReportListItem } from '../../lib/types/research'
import { formatAppDate } from '@/lib/utils/dateLocale'
import { readHistoryCache } from '@/features/history/historyCache'

interface RecentReportItemProps {
  report: ReportListItem;
  idx: number;
  onNavigate: (id: string) => void;
  t: (key: string) => string;
  language: string;
}

const RecentReportItem = memo(function RecentReportItem({ report, idx, onNavigate, t, language }: RecentReportItemProps) {
  return (
    <button
      onClick={() => onNavigate(report.id)}
      className="group block w-full text-left p-4 border-b-2 border-border/20 last:border-0 hover:bg-background/50 focus-visible:bg-background/50 transition-colors duration-150 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
    >
      <div className="flex gap-4 items-start">
        <span aria-hidden="true" className="text-3xl font-black text-muted-foreground/30 leading-none shrink-0">0{idx + 1}</span>
        <div className="min-w-0">
          <p className="text-lg font-bold text-foreground leading-tight group-hover:text-primary transition-colors line-clamp-2 break-words" title={report.query}>
            {report.query}
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2 sm:gap-3">
            <Badge variant="secondary" className="text-[10px] sm:text-xs">
              {formatAppDate(report.created_at, language)}
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

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

export function HomePage() {
  const navigate = useNavigate()
  const { t, i18n } = useTranslation()
  const language = i18n.resolvedLanguage ?? i18n.language
  const [cachedRecentReports] = useState<ReportListItem[] | null>(
    () => readHistoryCache()?.reports.slice(0, 5) ?? null,
  )
  useDocumentTitle(`${t('app.title')} — ${t('app.titleHighlight')}`)

  const [recentReports, setRecentReports] = useState<ReportListItem[]>(() => cachedRecentReports ?? [])
  const [recentReportsLoading, setRecentReportsLoading] = useState(() => cachedRecentReports === null)
  const [recentReportsError, setRecentReportsError] = useState<string | null>(null)

  const handleNavigate = useCallback((id: string) => {
    navigate(`/reports/${id}`)
  }, [navigate])

  useEffect(() => {
    const controller = new AbortController()
    listReports({ limit: 5, offset: 0, signal: controller.signal })
      .then(({ items }) => {
        setRecentReports(items)
        setRecentReportsError(null)
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        setRecentReportsError(t('home.errorLoadRecent'))
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setRecentReportsLoading(false)
        }
      })
    return () => controller.abort()
  }, [cachedRecentReports, t])

  const handleSubmit = useCallback((query: string) => {
    const validation = SearchBox.validateQuery(query)
    if (!validation.isValid) {
      return
    }
    navigate('/reports/new', { state: { query: validation.normalizedQuery } })
  }, [navigate])

  return (
    <div className="app-shell pt-8 pb-16 sm:pt-12">
      <div className="grid items-start gap-16 lg:grid-cols-[1fr_400px]">
        {/* Main Content Section */}
        <section className="py-12 lg:py-16 text-left animate-fade-in">
          <h1 className="mb-8 font-heading uppercase tracking-tighter leading-[0.9] text-6xl sm:text-8xl md:text-[7rem] break-words">
            {t('app.title')}
            <br />
            <span className="text-primary">{t('app.titleHighlight')}</span>
          </h1>

          <p className="mb-12 max-w-2xl text-xl md:text-2xl font-bold leading-snug text-muted-foreground border-l-4 border-primary pl-6 min-w-0 break-words">
            {t('home.description')}
          </p>

          <div className="mt-8">
            <SearchBox onSubmit={handleSubmit} />

            <div className="mt-8">
              <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-muted-foreground mb-4">{t('home.quickPrompts')}</h3>
              <div className="flex flex-wrap gap-2">
                {[0, 1, 2, 3].map(index => {
                  const prompt = t(`home.prompt${index}`)
                  return (
                    <Button
                      key={prompt}
                      variant="ghost"
                      onClick={() => handleSubmit(prompt)}
                      className="text-sm font-medium normal-case tracking-normal px-3 py-1.5 min-h-[44px] h-auto text-muted-foreground hover:text-foreground"
                      title={prompt}
                    >
                      <span className="truncate max-w-[200px]">{prompt}</span>
                    </Button>
                  )
                })}
              </div>
            </div>
          </div>
        </section>

        {/* Sidebar - Recent Research */}
        <aside className="lg:mt-32 card bg-secondary text-secondary-foreground animate-fade-in [animation-delay:150ms]">
          <h2 className="mb-8 text-2xl font-black uppercase tracking-tight border-b-4 border-border pb-4 break-words">
            {t('home.recentResearch')}
          </h2>

          {recentReportsError && (
            <Alert variant="warning" className="mb-6">
              <span className="font-bold">{recentReportsError}</span>
            </Alert>
          )}

          {!recentReportsError && recentReportsLoading && recentReports.length === 0 && (
            <div className="space-y-3" aria-label={t('loading.page')}>
              {Array.from({ length: 3 }).map((_, index) => (
                <div
                  key={index}
                  className="h-20 border-2 border-border bg-background/60 animate-pulse"
                />
              ))}
            </div>
          )}

          {recentReports.length > 0 && (
            <div className="space-y-0">
              {recentReports.map((report, idx) => (
                <RecentReportItem
                  key={report.id}
                  report={report}
                  idx={idx}
                  onNavigate={handleNavigate}
                  t={t}
                  language={language}
                />
              ))}
            </div>
          )}

          {!recentReportsError && !recentReportsLoading && recentReports.length === 0 && (
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
