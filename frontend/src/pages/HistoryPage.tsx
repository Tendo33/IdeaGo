import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2, Clock, Users, FileText } from 'lucide-react'
import { listReports, deleteReport } from '../api/client'
import type { ReportListItem } from '../types/research'

export function HistoryPage() {
  const navigate = useNavigate()
  const [reports, setReports] = useState<ReportListItem[]>([])
  const [loading, setLoading] = useState(true)

  const fetchReports = async () => {
    try {
      const data = await listReports()
      setReports(data)
    } catch {
      // ignore
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
    } catch {
      // ignore
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

        <h1 className="text-2xl font-bold font-[family-name:var(--font-heading)] text-text mb-6">
          Research History
        </h1>

        {loading && (
          <p className="text-text-muted text-sm">Loading...</p>
        )}

        {!loading && reports.length === 0 && (
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

        {reports.length > 0 && (
          <div className="space-y-2">
            {reports.map(report => (
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
      </div>
    </div>
  )
}
