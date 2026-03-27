import { useCallback, useEffect, useState, memo, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2, Clock, Users, FileText, Search, Loader2 } from 'lucide-react'
import { deleteReport, isRequestAbortError, listReports } from '@/lib/api/client'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Alert } from '@/components/ui/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button, buttonVariants } from '@/components/ui/Button'
import type { ReportListItem } from '@/lib/types/research'
import { formatAppDate } from '@/lib/utils/dateLocale'
import { readHistoryCache, writeHistoryCache, type HistoryCacheSnapshot } from '@/features/history/historyCache'

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

const PAGE_SIZE = 20

function openDialogElement(dialog: HTMLDialogElement | null) {
  if (!dialog) return
  if (typeof dialog.showModal === 'function') {
    dialog.showModal()
    return
  }
  dialog.setAttribute('open', '')
}

function closeDialogElement(dialog: HTMLDialogElement | null) {
  if (!dialog) return
  if (typeof dialog.close === 'function') {
    dialog.close()
    return
  }
  dialog.removeAttribute('open')
}

interface HistoryReportCardProps {
  report: ReportListItem;
  isDeleting: boolean;
  onNavigate: (id: string) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  t: (key: string) => string;
  language: string;
}

const HistoryReportCard = memo(function HistoryReportCard({ report, isDeleting, onDelete, t, language }: HistoryReportCardProps) {
  return (
    <div className="group relative flex flex-col sm:flex-row items-start sm:items-center justify-between border-2 border-border bg-card p-5 shadow hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-sm transition-all duration-150 focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2">
      <div className="mr-6 min-w-0 flex-1 mb-4 sm:mb-0">
        <Link
          to={`/reports/${report.id}`}
          className="truncate block text-lg sm:text-xl font-black text-foreground transition-colors duration-150 group-hover:text-primary outline-none before:absolute before:inset-0"
          title={report.query}
        >
          {report.query}
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-2 sm:gap-4 relative z-10 pointer-events-none">
          <Badge variant="secondary">
            <Clock className="h-3.5 w-3.5" />
            {formatAppDate(report.created_at, language)}
          </Badge>
          <Badge variant="accent">
            <Users className="h-3.5 w-3.5" />
            {report.competitor_count} {t('home.competitors')}
          </Badge>
        </div>
      </div>
      <button
        onClick={e => onDelete(report.id, e)}
        disabled={isDeleting}
        className="relative z-10 shrink-0 cursor-pointer border-2 border-border bg-background p-3 text-muted-foreground transition-all duration-150 hover:bg-destructive hover:text-destructive-foreground hover:shadow-sm focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        aria-label={isDeleting ? t('history.deleting') : t('history.delete')}
      >
        {isDeleting ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <Trash2 className="h-5 w-5" />
        )}
      </button>
    </div>
  )
})

export function HistoryPage() {
  const navigate = useNavigate()
  const { t, i18n } = useTranslation()
  const language = i18n.resolvedLanguage ?? i18n.language
  const [initialCache] = useState<HistoryCacheSnapshot | null>(() => readHistoryCache())
  useDocumentTitle(t('history.title') + ' — IdeaGo')
  const [reports, setReports] = useState<ReportListItem[]>(() => initialCache?.reports ?? [])
  const [loading, setLoading] = useState(() => initialCache === null)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set())
  const [reportToDelete, setReportToDelete] = useState<string | null>(null)
  const dialogRef = useRef<HTMLDialogElement>(null)
  const initialCacheUsedRef = useRef(false)

  useEffect(() => {
    if (reportToDelete) {
      openDialogElement(dialogRef.current)
    } else {
      closeDialogElement(dialogRef.current)
    }
  }, [reportToDelete])
  const [pageIndex, setPageIndex] = useState(() => initialCache?.pageIndex ?? 0)
  const [hasNextPage, setHasNextPage] = useState(() => initialCache?.hasNextPage ?? false)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(searchQuery.trim())
    }, 300)
    return () => window.clearTimeout(timer)
  }, [searchQuery])

  useEffect(() => {
    setPageIndex(0)
  }, [debouncedQuery])

  const loadPage = useCallback(async (targetPage: number, signal?: AbortSignal) => {
    const { items, total } = await listReports({
      limit: PAGE_SIZE,
      offset: targetPage * PAGE_SIZE,
      q: debouncedQuery,
      signal,
    })
    return {
      reports: items,
      hasNext: (targetPage + 1) * PAGE_SIZE < total,
    }
  }, [debouncedQuery])

  useEffect(() => {
    const controller = new AbortController()
    const canHydrateFromCache =
      !initialCacheUsedRef.current &&
      initialCache !== null &&
      initialCache.pageIndex === pageIndex &&
      debouncedQuery.length === 0

    initialCacheUsedRef.current = true
    if (!canHydrateFromCache) {
      setLoading(true)
    }

    loadPage(pageIndex, controller.signal)
      .then(({ reports: nextReports, hasNext }) => {
        if (!controller.signal.aborted && nextReports.length === 0 && pageIndex > 0) {
          setPageIndex(previous => Math.max(0, previous - 1))
          return
        }
        setReports(nextReports)
        setHasNextPage(hasNext)
        setError(null)
        if (!debouncedQuery) {
          writeHistoryCache({
            pageIndex,
            hasNextPage: hasNext,
            reports: nextReports,
          })
        }
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
  }, [debouncedQuery, initialCache, loadPage, pageIndex, t])

  const handleDeleteClick = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (deletingIds.has(id)) return
    setReportToDelete(id)
  }

  const confirmDelete = async () => {
    if (!reportToDelete) return
    const id = reportToDelete
    setReportToDelete(null)

    setDeletingIds(previous => {
      const next = new Set(previous)
      next.add(id)
      return next
    })
    setError(null)

    try {
      await deleteReport(id)
      toast.success(t('history.deleted', 'Report deleted'))
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
      writeHistoryCache({
        pageIndex: targetPage,
        hasNextPage: hasNext,
        reports: refreshed,
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : t('history.errorDelete')
      setError(msg)
      toast.error(msg)
    } finally {
      setDeletingIds(previous => {
        const next = new Set(previous)
        next.delete(id)
        return next
      })
    }
  }

  const handleNavigate = useCallback((id: string) => {
    navigate(`/reports/${id}`)
  }, [navigate])

  return (
    <>
      <div className="app-shell max-w-5xl pt-8 pb-16">
        <Link
          to="/"
          className={buttonVariants({ variant: 'secondary', size: 'sm', className: "mb-8" })}
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('history.back')}
        </Link>

        <div className="border-4 border-border bg-card p-6 md:p-10 mb-8 shadow-lg">
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
                  className="w-full border-2 border-border bg-background pl-12 pr-4 py-3 text-sm font-bold placeholder:text-muted-foreground/50 focus:outline-none focus:ring-0 focus:border-primary focus:shadow shadow-primary transition-all"
                />
              </div>
            )}
          </div>
        </div>

        {error && (
          <Alert variant="destructive" className="mb-8">
            <span className="font-bold">{error}</span>
          </Alert>
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
              className={buttonVariants({ variant: 'primary', size: 'md' })}
            >
              {t('history.startFirst')}
            </Link>
          </div>
        )}

        {reports.length > 0 && (
          <div className="space-y-4">
            {reports.map(report => (
              <HistoryReportCard
                key={report.id}
                report={report}
                isDeleting={deletingIds.has(report.id)}
                onNavigate={handleNavigate}
                onDelete={handleDeleteClick}
                t={t}
                language={language}
              />
            ))}
          </div>
        )}

        {!loading && reports.length === 0 && searchQuery.trim() && (
          <div className="py-12 text-center border-2 border-dashed border-border bg-muted/20">
            <p className="text-base font-bold uppercase tracking-widest text-muted-foreground">
              {t('history.noMatch', { query: searchQuery })}
            </p>
          </div>
        )}

        {!loading && !error && (reports.length > 0 || pageIndex > 0) && (
          <div className="mt-10 flex items-center justify-center gap-4">
            <Button
              variant="secondary"
              onClick={() => setPageIndex(previous => Math.max(0, previous - 1))}
              disabled={pageIndex === 0}
            >
              {t('history.prevPage')}
            </Button>
            <span className="text-sm font-black text-muted-foreground border-2 border-border bg-background px-4 py-2 shadow-sm">
              {t('history.pageLabel', { page: pageIndex + 1 })}
            </span>
            <Button
              variant="secondary"
              onClick={() => setPageIndex(previous => previous + 1)}
              disabled={!hasNextPage}
            >
              {t('history.nextPage')}
            </Button>
          </div>
        )}
      </div>

      <dialog
        ref={dialogRef}
        className="fixed inset-0 z-50 m-auto bg-transparent p-4 open:animate-fade-in backdrop:bg-foreground/45"
        onCancel={() => setReportToDelete(null)}
        onClick={(e) => {
          if (e.target === dialogRef.current) setReportToDelete(null)
        }}
      >
        <div
          className="bg-card border-4 border-border shadow-lg p-6 max-w-sm w-full"
          onClick={e => e.stopPropagation()}
        >
          <h3 id="delete-dialog-title" className="text-xl font-black uppercase tracking-tight mb-2 text-foreground">
            {t('history.deleteConfirmTitle')}
          </h3>
          <p className="text-sm font-medium text-muted-foreground mb-6">
            {t('history.deleteConfirm')}
          </p>
          <div className="flex gap-3 justify-end">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setReportToDelete(null)}
            >
              {t('common.cancel')}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={confirmDelete}
            >
              {t('common.delete')}
            </Button>
          </div>
        </div>
      </dialog>
    </>
  )
}
