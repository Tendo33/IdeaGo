import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Users, FileText, Loader2, Activity, Save } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Alert } from '@/components/ui/Alert'
import {
  adminGetStats,
  adminListUsers,
  adminSetQuota,
  type AdminStats,
  type AdminUser,
} from '@/lib/api/client'

function StatCard({ label, value, icon: Icon }: { label: string; value: string | number; icon: typeof Users }) {
  return (
    <div className="border-4 border-border bg-card p-6 shadow">
      <div className="flex items-center gap-3 mb-3">
        <Icon className="w-5 h-5 text-primary" />
        <span className="text-xs font-black uppercase tracking-widest text-muted-foreground">{label}</span>
      </div>
      <p className="text-4xl font-black text-foreground leading-none">{value}</p>
    </div>
  )
}

function UserRow({ user, onQuotaSaved }: { user: AdminUser; onQuotaSaved: () => void }) {
  const [editing, setEditing] = useState(false)
  const [limit, setLimit] = useState(String(user.plan_limit))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    setSaving(true)
    setError('')
    try {
      await adminSetQuota(user.id, { plan_limit: Number(limit) })
      setEditing(false)
      onQuotaSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className="border-b-2 border-border/30 hover:bg-muted/30 transition-colors">
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          {user.avatar_url ? (
            <img src={user.avatar_url} alt="" className="w-8 h-8 border-2 border-border" />
          ) : (
            <div className="w-8 h-8 border-2 border-border bg-muted" />
          )}
          <div className="min-w-0">
            <p className="text-sm font-bold truncate">{user.display_name || '(unnamed)'}</p>
            <p className="text-xs text-muted-foreground truncate">{user.id.slice(0, 12)}...</p>
          </div>
        </div>
      </td>
      <td className="py-3 px-4">
        <Badge variant={user.role === 'admin' ? 'primary' : 'secondary'} className="text-[10px]">
          {user.role}
        </Badge>
      </td>
      <td className="py-3 px-4 text-sm font-mono">{user.plan}</td>
      <td className="py-3 px-4 text-sm font-mono">{user.auth_provider}</td>
      <td className="py-3 px-4 text-sm font-mono">{user.usage_count}</td>
      <td className="py-3 px-4">
        {editing ? (
          <div className="flex items-center gap-2">
            <input
              type="number"
              value={limit}
              onChange={e => setLimit(e.target.value)}
              className="input w-20 py-1 px-2 text-sm"
              min={0}
            />
            <button
              onClick={save}
              disabled={saving}
              className="text-primary hover:text-foreground transition-colors cursor-pointer"
              aria-label="Save"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            </button>
            {error && <span className="text-xs text-destructive">{error}</span>}
          </div>
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-sm font-mono text-muted-foreground hover:text-foreground transition-colors cursor-pointer underline underline-offset-2"
          >
            {user.plan_limit}
          </button>
        )}
      </td>
      <td className="py-3 px-4 text-xs text-muted-foreground">
        {new Date(user.created_at).toLocaleDateString()}
      </td>
    </tr>
  )
}

export function AdminPage() {
  const { t } = useTranslation()
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [s, u] = await Promise.all([adminGetStats(), adminListUsers({ limit: 100 })])
      setStats(s)
      setUsers(u)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load admin data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="min-h-screen px-4 py-8 bg-background text-foreground">
      <div className="app-shell max-w-6xl">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('nav.home', 'Home')}
        </Link>

        <h1 className="text-4xl font-black uppercase tracking-tight mb-8 border-b-4 border-border pb-4">
          {t('admin.title', 'Admin Dashboard')}
        </h1>

        {error && (
          <Alert variant="warning" className="mb-6">
            <span className="font-bold">{error}</span>
          </Alert>
        )}

        {loading && (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        )}

        {!loading && stats && (
          <>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
              <StatCard label={t('admin.totalUsers', 'Users')} value={stats.total_users} icon={Users} />
              <StatCard label={t('admin.totalReports', 'Reports')} value={stats.total_reports} icon={FileText} />
              <StatCard label={t('admin.activeProcessing', 'Processing')} value={stats.active_processing} icon={Activity} />
              <StatCard
                label={t('admin.planBreakdown', 'Plans')}
                value={Object.entries(stats.plan_breakdown).map(([k, v]) => `${k}:${v}`).join(' ')}
                icon={Users}
              />
            </div>

            <h2 className="text-2xl font-black uppercase tracking-tight mb-4">
              {t('admin.usersTitle', 'Users')}
            </h2>

            <div className="overflow-x-auto border-4 border-border">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b-4 border-border bg-muted">
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.user', 'User')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.role', 'Role')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.plan', 'Plan')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.provider', 'Provider')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.usage', 'Usage')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.limit', 'Limit')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.joined', 'Joined')}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(user => (
                    <UserRow key={user.id} user={user} onQuotaSaved={load} />
                  ))}
                </tbody>
              </table>
            </div>

            {users.length === 0 && (
              <p className="text-center text-muted-foreground py-8 font-bold">
                {t('admin.noUsers', 'No users found.')}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
