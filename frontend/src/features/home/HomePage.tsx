import { useEffect, useState, memo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { X } from 'lucide-react'
import { SearchBox } from './components/SearchBox'
import { isRequestAbortError, listReports } from '../../lib/api/client'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../lib/auth/useAuth'
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

const WELCOME_DISMISSED_KEY = 'ideago_welcome_dismissed'

function WelcomeBanner() {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(true)

  if (!visible) return null

  const dismiss = () => {
    localStorage.setItem(WELCOME_DISMISSED_KEY, '1')
    setVisible(false)
  }

  return (
    <div className="relative mb-8 border-4 border-primary bg-primary/5 p-6 animate-fade-in">
      <button
        onClick={dismiss}
        className="absolute top-3 right-3 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        aria-label={t('common.dismiss', 'Dismiss')}
      >
        <X className="w-5 h-5" />
      </button>
      <h3 className="text-lg font-black uppercase tracking-tight mb-2">
        {t('welcome.title', 'Welcome to IdeaGo!')}
      </h3>
      <p className="text-sm text-muted-foreground font-medium leading-relaxed max-w-xl">
        {t('welcome.body', 'Describe your startup idea below and we\'ll find competitors, analyze market signals, and generate a research report in minutes.')}
      </p>
      <div className="mt-4 flex flex-wrap gap-4 text-xs font-bold uppercase tracking-widest text-muted-foreground/70">
        <span>1. {t('welcome.step1', 'Enter your idea')}</span>
        <span>2. {t('welcome.step2', 'AI researches the market')}</span>
        <span>3. {t('welcome.step3', 'Read your report')}</span>
      </div>
    </div>
  )
}

export function HomePage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { user } = useAuth()
  const [recentReports, setRecentReports] = useState<ReportListItem[]>([])
  const [recentReportsError, setRecentReportsError] = useState<string | null>(null)
  const showWelcome = user && !localStorage.getItem(WELCOME_DISMISSED_KEY)

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

        {showWelcome && (
          <div className="lg:col-span-2">
            <WelcomeBanner />
          </div>
        )}

        {/* Main Content Section */}
        <section className="py-12 lg:py-16 text-left animate-fade-in">
          <h1 className="mb-8 font-heading uppercase tracking-tighter leading-[0.9] text-6xl sm:text-8xl md:text-[7rem] break-words wrap">
            {t('app.title')}
            <br />
            <span className="text-primary">{t('app.titleHighlight')}</span>
          </h1>

          <p className="mb-12 max-w-2xl text-xl md:text-2xl font-bold leading-snug text-muted-foreground border-l-4 border-primary pl-6 wrap min-w-0 break-words">
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

          {recentReports.length > 0 && (
            <div className="space-y-0">
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
