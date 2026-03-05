import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2, Clock, Users, FileText, AlertCircle, Search, Loader2 } from 'lucide-react'
import { deleteReport, isRequestAbortError, listReports } from '../api/client'
import { ReportCardSkeleton } from '../components/Skeleton'
import { useTranslation } from 'react-i18next'
import type { ReportListItem } from '../types/research'

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
    <div className="min-h-screen px-4 pb-12 pt-8">
      <div className="app-shell max-w-5xl">
        <Link
          to="/"
          className="mb-4 inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1 text-sm text-text-dim transition-colors duration-300 hover:text-text hover:bg-muted/55"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('history.back')}
        </Link>

        <div className="rounded-2xl border border-border/80 bg-card/85 backdrop-blur-xl shadow-xl mb-6 px-5 py-5 sm:px-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="text-2xl font-bold text-text sm:text-3xl">
              {t('history.title')}
            </h1>
            {reports.length > 0 && (
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-dim" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder={t('history.filterPlaceholder')}
                  className="input w-full bg-card/85 pl-9 pr-3 py-2 text-sm text-text placeholder-text-dim sm:w-64 border-border/80 focus:border-cta"
                />
              </div>
            )}
          </div>
          <p className="mt-2 text-sm text-text-muted">
            {t('home.description')}
          </p>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-danger/25 bg-danger/10 px-4 py-3">
            <AlertCircle className="h-4 w-4 shrink-0 text-danger" />
            <p className="text-sm text-danger">{error}</p>
          </div>
        )}

        {loading && (
          <div className="space-y-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <ReportCardSkeleton key={i} />
            ))}
          </div>
        )}

        {!loading && !error && reports.length === 0 && (
          <div className="rounded-2xl border border-border/80 bg-card/85 backdrop-blur-xl p-12 text-center shadow-xl">
            <FileText className="mx-auto mb-3 h-10 w-10 text-text-dim" />
            <p className="mb-4 text-sm text-text-muted">{t('history.emptyState')}</p>
            <Link
              to="/"
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-cta px-4 py-2 text-sm font-medium text-primary-foreground transition-colors duration-200 hover:bg-cta-hover"
            >
              {t('history.startFirst')}
            </Link>
          </div>
        )}

        {filtered.length > 0 && (
          <div className="space-y-2.5">
            {filtered.map(report => (
              <div
                key={report.id}
                onClick={() => navigate(`/reports/${report.id}`)}
                className="group interactive-surface flex items-center justify-between px-5 py-4 hover:-translate-y-px cursor-pointer"
                role="button"
                tabIndex={0}
                onKeyDown={e => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    navigate(`/reports/${report.id}`)
                  }
                }}
              >
                <div className="mr-4 min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-text transition-colors duration-300 group-hover:text-cta">
                    {report.query}
                  </p>
                  <div className="mt-1.5 flex items-center gap-4">
                    <span className="inline-flex items-center gap-1 text-xs text-text-dim">
                      <Clock className="h-3 w-3" />
                      {new Date(report.created_at).toLocaleDateString()}
                    </span>
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-cta">
                      <Users className="h-3 w-3" />
                      {report.competitor_count} {t('home.competitors')}
                    </span>
                  </div>
                </div>
                <button
                  onClick={e => handleDelete(report.id, e)}
                  disabled={deletingIds.has(report.id)}
                  className="cursor-pointer rounded-lg p-2 text-text-dim transition-colors duration-200 hover:bg-danger/10 hover:text-danger focus:outline-none focus:ring-2 focus:ring-danger/30 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent disabled:hover:text-text-dim"
                  aria-label={deletingIds.has(report.id) ? t('history.deleting') : t('history.delete')}
                >
                  {deletingIds.has(report.id) ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}

        {!loading && reports.length > 0 && filtered.length === 0 && searchQuery.trim() && (
          <p className="py-8 text-center text-sm text-text-dim">{t('history.noMatch', { query: searchQuery })}</p>
        )}

        {!loading && !error && (reports.length > 0 || pageIndex > 0) && (
          <div className="mt-6 flex items-center justify-center gap-3">
            <button
              onClick={() => setPageIndex(previous => Math.max(0, previous - 1))}
              disabled={pageIndex === 0}
              className="filter-chip rounded-lg px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t('history.prevPage')}
            </button>
            <span className="text-xs text-text-dim">
              {t('history.pageLabel', { page: pageIndex + 1 })}
            </span>
            <button
              onClick={() => setPageIndex(previous => previous + 1)}
              disabled={!hasNextPage}
              className="filter-chip rounded-lg px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t('history.nextPage')}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
