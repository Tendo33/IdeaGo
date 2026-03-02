import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2, Clock, Users, FileText, AlertCircle, Search, Loader2 } from 'lucide-react'
import { deleteReport, isRequestAbortError, listReports } from '../api/client'
import { ReportCardSkeleton } from '../components/Skeleton'
import { useTranslation } from 'react-i18next'
import type { ReportListItem } from '../types/research'

export function HistoryPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return reports
    const q = searchQuery.toLowerCase()
    return reports.filter(r => r.query.toLowerCase().includes(q))
  }, [reports, searchQuery])

  useEffect(() => {
    const controller = new AbortController()
    listReports({ signal: controller.signal })
      .then(data => {
        setReports(data)
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
  }, [t])

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
      setReports(prev => prev.filter(r => r.id !== id))
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
          className="mb-4 inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1 text-sm text-text-muted transition-colors duration-200 hover:text-primary"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('history.back')}
        </Link>

        <div className="surface-card mb-6 bg-gradient-to-r from-white to-primary/5 px-5 py-5 sm:px-6">
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
                  className="input w-full bg-bg-card pl-9 pr-3 py-2 text-sm text-text placeholder-text-dim sm:w-64"
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
          <div className="surface-card p-12 text-center">
            <FileText className="mx-auto mb-3 h-10 w-10 text-text-dim" />
            <p className="mb-4 text-sm text-text-muted">{t('history.emptyState')}</p>
            <Link
              to="/"
              className="inline-flex cursor-pointer items-center gap-2 rounded-xl bg-cta px-4 py-2 text-sm font-medium text-white transition-colors duration-200 hover:bg-cta-hover"
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
                className="group card card-clickable flex items-center justify-between px-4 py-4"
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
                  <p className="truncate text-sm font-semibold text-text transition-colors duration-200 group-hover:text-primary">
                    {report.query}
                  </p>
                  <div className="mt-1.5 flex items-center gap-4">
                    <span className="inline-flex items-center gap-1 text-xs text-text-dim">
                      <Clock className="h-3 w-3" />
                      {new Date(report.created_at).toLocaleDateString()}
                    </span>
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-primary">
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
      </div>
    </div>
  )
}
