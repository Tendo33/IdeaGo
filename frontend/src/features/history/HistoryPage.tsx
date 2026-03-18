import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2, Clock, Users, FileText, AlertCircle, Search, Loader2 } from 'lucide-react'
import { deleteReport, isRequestAbortError, listReports } from '../../lib/api/client'
import { useTranslation } from 'react-i18next'
import type { ReportListItem } from '../../lib/types/research'

const PAGE_SIZE = 20
const PAGE_FETCH_LIMIT = PAGE_SIZE + 1

export function HistoryPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const [pageIndex, setPageIndex] = useState(0)
  const [hasNextPage, setHasNextPage] = useState(false)

  const loadPage = useCallback(async (targetPage: number, signal?: AbortSignal) => {
    const fetched = await listReports({
      limit: PAGE_FETCH_LIMIT,
      offset: targetPage * PAGE_SIZE,
      signal,
    })
    return {
      reports: fetched.slice(0, PAGE_SIZE),
      hasNext: fetched.length > PAGE_SIZE,
    }
  }, [])

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return reports
    const q = searchQuery.toLowerCase()
    return reports.filter(r => r.query.toLowerCase().includes(q))
  }, [reports, searchQuery])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    loadPage(pageIndex, controller.signal)
      .then(({ reports: nextReports, hasNext }) => {
        if (!controller.signal.aborted && nextReports.length === 0 && pageIndex > 0) {
          setPageIndex(previous => Math.max(0, previous - 1))
          return
        }
        setReports(nextReports)
        setHasNextPage(hasNext)
        setError(null)
      })
      .catch(error => {
        if (isRequestAbortError(error)) return
        setError(error instanceof Error ? error.message : t('history.errorLoad'))
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })
    return () => controller.abort()
  }, [loadPage, pageIndex, t])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (deletingIds.has(id)) return
    if (!window.confirm(t('history.deleteConfirm'))) return

    setDeletingIds(previous => {
      const next = new Set(previous)
      next.add(id)
      return next
    })
    setError(null)

    try {
      await deleteReport(id)
      const targetPage = reports.length === 1 && pageIndex > 0 ? pageIndex - 1 : pageIndex
      if (targetPage !== pageIndex) {
        setPageIndex(targetPage)
        return
      }

      const { reports: refreshed, hasNext } = await loadPage(targetPage)
      if (refreshed.length === 0 && targetPage > 0) {
        setPageIndex(targetPage - 1)
        return
      }
      setReports(refreshed)
      setHasNextPage(hasNext)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('history.errorDelete'))
    } finally {
      setDeletingIds(previous => {
        const next = new Set(previous)
        next.delete(id)
        return next
      })
    }
  }

  return (
    <div className="min-h-screen px-4 pb-16 pt-12 bg-background text-foreground">
      <div className="app-shell max-w-5xl">
        <Link
          to="/"
          className="mb-8 inline-flex cursor-pointer items-center gap-2 border-2 border-border px-4 py-2 text-sm font-bold uppercase tracking-widest text-foreground transition-all duration-150 shadow-[4px_4px_0px_0px_var(--border)] hover:bg-primary hover:text-primary-foreground hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)]"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('history.back')}
        </Link>

        <div className="border-4 border-border bg-card p-6 md:p-10 mb-8 shadow-[8px_8px_0px_0px_var(--border)]">
          <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div>
              <h1 className="text-4xl md:text-5xl font-black uppercase tracking-tighter mb-2">
                {t('history.title')}
              </h1>
              <p className="text-lg font-bold text-muted-foreground uppercase tracking-widest border-l-4 border-primary pl-4">
                {t('home.description')}
              </p>
            </div>
            {reports.length > 0 && (
              <div className="relative w-full md:w-80">
                <Search className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder={t('history.filterPlaceholder')}
                  className="w-full border-2 border-border bg-background pl-12 pr-4 py-3 text-sm font-bold placeholder:text-muted-foreground/50 focus:outline-none focus:ring-0 focus:border-primary focus:shadow-[4px_4px_0px_0px_var(--primary)] transition-all"
                />
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-8 flex items-start gap-3 border-2 border-destructive bg-destructive/10 p-5 shadow-[4px_4px_0px_0px_var(--destructive)]">
            <AlertCircle className="h-6 w-6 shrink-0 text-destructive" />
            <p className="text-sm font-bold text-destructive">{error}</p>
          </div>
        )}

        {loading && (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-24 w-full bg-muted border-2 border-border animate-pulse"></div>
            ))}
          </div>
        )}

        {!loading && !error && reports.length === 0 && (
          <div className="border-4 border-dashed border-border bg-card p-16 text-center shadow-none">
            <FileText className="mx-auto mb-4 h-12 w-12 text-muted-foreground/50" />
            <p className="mb-6 text-lg font-bold uppercase tracking-widest text-muted-foreground">{t('history.emptyState')}</p>
            <Link
              to="/"
              className="inline-flex cursor-pointer items-center gap-2 bg-primary px-6 py-3 text-sm font-black uppercase tracking-widest text-primary-foreground border-2 border-border shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] transition-all duration-150"
            >
              {t('history.startFirst')}
            </Link>
          </div>
        )}

        {filtered.length > 0 && (
          <div className="space-y-4">
            {filtered.map(report => (
              <div
                key={report.id}
                onClick={() => navigate(`/reports/${report.id}`)}
                className="group flex flex-col sm:flex-row items-start sm:items-center justify-between border-2 border-border bg-card p-5 shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] transition-all duration-150 cursor-pointer"
                role="button"
                tabIndex={0}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/reports/${report.id}`)
                  }
                }}
              >
                <div className="mr-6 min-w-0 flex-1 mb-4 sm:mb-0">
                  <p className="truncate text-xl font-black text-foreground transition-colors duration-150 group-hover:text-primary">
                    {report.query}
                  </p>
                  <div className="mt-3 flex flex-wrap items-center gap-4">
                    <span className="inline-flex items-center gap-1.5 border border-border bg-background px-2 py-1 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      {new Date(report.created_at).toLocaleDateString()}
                    </span>
                    <span className="inline-flex items-center gap-1.5 border border-border bg-primary/10 px-2 py-1 text-xs font-black uppercase tracking-wider text-primary">
                      <Users className="h-3.5 w-3.5" />
                      {report.competitor_count} {t('home.competitors')}
                    </span>
                  </div>
                </div>
                <button
                  onClick={e => handleDelete(report.id, e)}
                  disabled={deletingIds.has(report.id)}
                  className="shrink-0 cursor-pointer border-2 border-border bg-background p-3 text-muted-foreground transition-all duration-150 hover:bg-destructive hover:text-destructive-foreground hover:shadow-[2px_2px_0px_0px_var(--border)] disabled:cursor-not-allowed disabled:opacity-50"
                  aria-label={deletingIds.has(report.id) ? t('history.deleting') : t('history.delete')}
                >
                  {deletingIds.has(report.id) ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <Trash2 className="h-5 w-5" />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}

        {!loading && reports.length > 0 && filtered.length === 0 && searchQuery.trim() && (
          <div className="py-12 text-center border-2 border-dashed border-border bg-muted/20">
            <p className="text-base font-bold uppercase tracking-widest text-muted-foreground">
              {t('history.noMatch', { query: searchQuery })}
            </p>
          </div>
        )}

        {!loading && !error && (reports.length > 0 || pageIndex > 0) && (
          <div className="mt-10 flex items-center justify-center gap-4">
            <button
              onClick={() => setPageIndex(previous => Math.max(0, previous - 1))}
              disabled={pageIndex === 0}
              className="border-2 border-border bg-card px-4 py-2 font-bold uppercase tracking-widest transition-all shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:shadow-[4px_4px_0px_0px_var(--border)]"
            >
              {t('history.prevPage')}
            </button>
            <span className="text-sm font-black text-muted-foreground border-2 border-border bg-background px-4 py-2">
              {t('history.pageLabel', { page: pageIndex + 1 })}
            </span>
            <button
              onClick={() => setPageIndex(previous => previous + 1)}
              disabled={!hasNextPage}
              className="border-2 border-border bg-card px-4 py-2 font-bold uppercase tracking-widest transition-all shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:shadow-[4px_4px_0px_0px_var(--border)]"
            >
              {t('history.nextPage')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
