import { useCallback, useEffect, useState } from 'react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'
import { ArrowLeft, Users, FileText, Loader2, Activity, Save } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/Badge'
import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import {
  adminGetStats,
  adminListUsers,
  adminSetQuota,
  type AdminStats,
  type AdminUser,
} from '@/lib/api/client'
import { formatAppDate } from '@/lib/utils/dateLocale'

function getAdminRoleLabel(role: string, t: TFunction): string {
  if (role === 'admin') return t('admin.values.roles.admin')
  if (role === 'user') return t('admin.values.roles.user')
  return role
}

function getAdminPlanLabel(plan: string, t: TFunction): string {
  if (plan === 'free') return t('admin.values.plans.free')
  if (plan === 'pro') return t('admin.values.plans.pro')
  return plan
}

function getAdminProviderLabel(provider: string, t: TFunction): string {
  if (provider === 'github') return t('admin.values.providers.github')
  if (provider === 'google') return t('admin.values.providers.google')
  if (provider === 'linuxdo') return t('admin.values.providers.linuxdo')
  if (provider === 'supabase') return t('admin.values.providers.supabase')
  return provider
}

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

function UserRow({ user, onQuotaSaved, language }: { user: AdminUser; onQuotaSaved: () => void; language: string }) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [limit, setLimit] = useState(String(user.plan_limit))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [imgError, setImgError] = useState(false)
  const displayName = user.display_name || t('admin.userFallbackName')
  const quotaTargetName = user.display_name || user.id.slice(0, 8)

  const save = async () => {
    setSaving(true)
    setError('')
    try {
      await adminSetQuota(user.id, { plan_limit: Number(limit) })
      setEditing(false)
      toast.success(t('admin.messages.quotaUpdated', { name: quotaTargetName }))
      onQuotaSaved()
    } catch (e) {
      const msg = e instanceof Error ? e.message : t('admin.messages.unknownError')
      setError(msg)
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <tr className="border-b-2 border-border/30 hover:bg-muted/30 transition-colors">
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          {user.avatar_url && !imgError ? (
            <img src={user.avatar_url} alt="" onError={() => setImgError(true)} className="w-8 h-8 border-2 border-border" />
          ) : (
            <div className="w-8 h-8 border-2 border-border bg-muted flex items-center justify-center text-[10px] font-black">
              {(user.display_name || user.id).charAt(0).toUpperCase()}
            </div>
          )}
          <div className="min-w-0">
            <p className="text-sm font-bold truncate">{displayName}</p>
            <p className="text-xs text-muted-foreground truncate">{user.id.slice(0, 12)}...</p>
          </div>
        </div>
      </td>
      <td className="py-3 px-4">
        <Badge variant={user.role === 'admin' ? 'primary' : 'secondary'} className="text-[10px]">
          {getAdminRoleLabel(user.role, t)}
        </Badge>
      </td>
      <td className="py-3 px-4 text-sm font-mono">{getAdminPlanLabel(user.plan, t)}</td>
      <td className="py-3 px-4 text-sm font-mono">{getAdminProviderLabel(user.auth_provider, t)}</td>
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
              aria-label={t('admin.actions.editQuotaFor', { name: quotaTargetName })}
            />
            <Button
              type="button"
              variant="secondary"
              size="icon"
              onClick={save}
              disabled={saving}
              className="h-9 w-9 text-primary"
              aria-label={t('admin.actions.saveQuotaFor', { name: quotaTargetName })}
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            </Button>
            {error && <span className="text-xs text-destructive">{error}</span>}
          </div>
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-sm font-mono text-muted-foreground hover:text-foreground transition-colors cursor-pointer underline underline-offset-2 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          >
            {user.plan_limit}
          </button>
        )}
      </td>
      <td className="py-3 px-4 text-xs text-muted-foreground">
        {formatAppDate(user.created_at, language)}
      </td>
    </tr>
  )
}

export function AdminPage() {
  const { t, i18n } = useTranslation()
  const language = i18n.resolvedLanguage ?? i18n.language
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
      setError(e instanceof Error ? e.message : t('admin.messages.loadError'))
    } finally {
      setLoading(false)
    }
  }, [t])

  useEffect(() => { load() }, [load])

  return (
    <div className="min-h-screen px-4 py-8 bg-background text-foreground">
      <div className="app-shell max-w-6xl">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          {t('nav.home')}
        </Link>

        <h1 className="text-4xl font-black uppercase tracking-tight mb-8 border-b-4 border-border pb-4">
          {t('admin.title')}
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
              <StatCard label={t('admin.totalUsers')} value={stats.total_users} icon={Users} />
              <StatCard label={t('admin.totalReports')} value={stats.total_reports} icon={FileText} />
              <StatCard label={t('admin.activeProcessing')} value={stats.active_processing} icon={Activity} />
              <StatCard
                label={t('admin.planBreakdown')}
                value={Object.entries(stats.plan_breakdown).map(([k, v]) => `${getAdminPlanLabel(k, t)}: ${v}`).join(' · ')}
                icon={Users}
              />
            </div>

            <h2 className="text-2xl font-black uppercase tracking-tight mb-4">
              {t('admin.usersTitle')}
            </h2>

            <div className="overflow-x-auto border-4 border-border">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b-4 border-border bg-muted">
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.user')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.role')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.plan')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.provider')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.usage')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.limit')}</th>
                    <th className="py-3 px-4 text-xs font-black uppercase tracking-widest">{t('admin.col.joined')}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(user => (
                    <UserRow key={user.id} user={user} onQuotaSaved={load} language={language} />
                  ))}
                </tbody>
              </table>
            </div>

            {users.length === 0 && (
              <p className="text-center text-muted-foreground py-8 font-bold">
                {t('admin.noUsers')}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}
