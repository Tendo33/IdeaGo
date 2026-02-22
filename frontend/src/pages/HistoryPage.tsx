import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2, Clock, Users, FileText, AlertCircle, Search } from 'lucide-react'
import { listReports, deleteReport } from '../api/client'
import { ReportCardSkeleton } from '../components/Skeleton'
import type { ReportListItem } from '../types/research'

export function HistoryPage() {
  const navigate = useNavigate()
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const filtered = useMemo(() => {
    if (!searchQuery.trim()) return reports
    const q = searchQuery.toLowerCase()
    return reports.filter(r => r.query.toLowerCase().includes(q))
  }, [reports, searchQuery])

  const fetchReports = async () => {
    setError(null)
    try {
      const data = await listReports()
      setReports(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load reports.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchReports() }, [])

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Delete this report?')) return
    try {
      await deleteReport(id)
      setReports(prev => prev.filter(r => r.id !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete report.')
    }
  }

  return (
    <div className="min-h-screen px-4 py-8">
      <div className="max-w-3xl mx-auto">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-cta transition-colors duration-200 mb-6 cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to search
        </Link>

        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
          <h1 className="text-2xl font-bold font-[family-name:var(--font-heading)] text-text">
            Research History
          </h1>
          {reports.length > 0 && (
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-dim" />
              <input
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Filter reports..."
                className="pl-9 pr-3 py-2 text-sm rounded-lg border border-border bg-bg-card text-text placeholder-text-dim transition-colors duration-200 focus:outline-none focus:border-cta focus:ring-2 focus:ring-cta/20 w-full sm:w-56"
              />
            </div>
          )}
        </div>

        {error && (
          <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-danger/10 border border-danger/30 mb-4">
            <AlertCircle className="w-4 h-4 text-danger shrink-0" />
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
          <div className="p-12 rounded-xl bg-bg-card border border-border text-center">
            <FileText className="w-10 h-10 text-text-dim mx-auto mb-3" />
            <p className="text-text-muted text-sm mb-4">No research reports yet.</p>
            <Link
              to="/"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cta text-white text-sm font-medium cursor-pointer transition-colors duration-200 hover:bg-cta-hover"
            >
              Start your first research
            </Link>
          </div>
        )}

        {filtered.length > 0 && (
          <div className="space-y-2">
            {filtered.map(report => (
              <div
                key={report.id}
                onClick={() => navigate(`/reports/${report.id}`)}
                className="flex items-center justify-between px-4 py-4 rounded-xl bg-bg-card border border-border cursor-pointer transition-all duration-200 hover:border-cta/30 hover:bg-bg-card-hover group"
                role="button"
                tabIndex={0}
                onKeyDown={e => { if (e.key === 'Enter') navigate(`/reports/${report.id}`) }}
              >
                <div className="min-w-0 flex-1 mr-4">
                  <p className="text-sm text-text font-medium truncate group-hover:text-cta transition-colors duration-200">
                    {report.query}
                  </p>
                  <div className="flex items-center gap-4 mt-1.5">
                    <span className="text-xs text-text-dim flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {new Date(report.created_at).toLocaleDateString()}
                    </span>
                    <span className="text-xs text-text-dim flex items-center gap-1">
                      <Users className="w-3 h-3" />
                      {report.competitor_count} competitors
                    </span>
                  </div>
                </div>
                <button
                  onClick={e => handleDelete(report.id, e)}
                  className="p-2 rounded-lg text-text-dim hover:text-danger hover:bg-danger/10 transition-colors duration-200 cursor-pointer focus:outline-none focus:ring-2 focus:ring-danger/30"
                  aria-label="Delete report"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {!loading && reports.length > 0 && filtered.length === 0 && searchQuery.trim() && (
          <p className="text-center text-sm text-text-dim py-8">No reports match &ldquo;{searchQuery}&rdquo;</p>
        )}
      </div>
    </div>
  )
}
