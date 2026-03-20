import { Button } from '@/components/ui/Button'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/lib/auth/useAuth'
import {
  getMyProfile,
  getQuotaInfo,
  updateMyProfile,
  type QuotaInfo,
  type UserProfile,
} from '@/lib/api/client'
import { ArrowLeft, Save, Loader2, User, Mail, FileText, Shield, BarChart3 } from 'lucide-react'

export function ProfilePage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [quota, setQuota] = useState<QuotaInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [displayName, setDisplayName] = useState('')
  const [bio, setBio] = useState('')

  useEffect(() => {
    if (!user) return
    let cancelled = false

    async function load() {
      const [profileResult, quotaResult] = await Promise.allSettled([
        getMyProfile(),
        getQuotaInfo(),
      ])

      if (cancelled) return

      if (profileResult.status === 'fulfilled') {
        const data = profileResult.value
        setProfile(data)
        setDisplayName(data.display_name)
        setBio(data.bio)
      } else {
        const msg = profileResult.reason?.message
        setError(msg ?? t('profile.loadError'))
      }

      if (quotaResult.status === 'fulfilled') {
        setQuota(quotaResult.value)
      }

      setLoading(false)
    }
    load()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user) return
    setError('')
    setSuccess('')
    setSaving(true)
    try {
      const updated = await updateMyProfile({
        display_name: displayName.trim(),
        bio: bio.trim(),
      })
      setProfile(updated)
      setSuccess(t('profile.saved', 'Profile updated successfully'))
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      const message = err instanceof Error ? err.message : t('profile.updateError')
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
        <div className="border-4 border-border bg-card px-12 py-8 text-center shadow-[8px_8px_0px_0px_var(--border)]">
          <div className="w-8 h-8 bg-primary border-2 border-border mx-auto mb-4 animate-spin" />
          <p className="text-sm font-black uppercase tracking-widest text-muted-foreground">
            {t('loading.page', 'Loading...')}
          </p>
        </div>
      </div>
    )
  }

  const avatarInitial = (displayName || user?.email || 'U').charAt(0).toUpperCase()
  const memberSince = profile?.created_at
    ? new Date(profile.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long' })
    : ''

  const usagePercent = quota && quota.plan_limit > 0
    ? Math.min(100, Math.round((quota.usage_count / quota.plan_limit) * 100))
    : 0

  return (
    <div className="app-shell px-4 max-w-2xl">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors mb-8"
      >
        <ArrowLeft className="w-4 h-4" />
        {t('nav.home', 'Home')}
      </Link>

      <h1 className="text-3xl md:text-4xl font-black uppercase tracking-tight mb-8">
        {t('profile.title', 'Profile')}
      </h1>

      {/* Avatar + info header */}
      <div className="border-4 border-border bg-card p-6 md:p-8 shadow-[6px_6px_0px_0px_var(--border)] mb-8">
        <div className="flex items-center gap-6">
          {profile?.avatar_url ? (
            <img
              src={profile.avatar_url}
              alt=""
              className="w-20 h-20 border-4 border-border object-cover"
            />
          ) : (
            <div className="w-20 h-20 bg-primary text-primary-foreground border-4 border-border flex items-center justify-center text-3xl font-black">
              {avatarInitial}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-black truncate">
              {displayName || user?.email || 'User'}
            </h2>
            <p className="text-sm text-muted-foreground font-bold truncate">{user?.email}</p>
            {memberSince && (
              <p className="text-xs text-muted-foreground mt-1">
                {t('profile.memberSince', 'Member since')} {memberSince}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Plan & usage card */}
      <div className="border-4 border-border bg-card p-6 md:p-8 shadow-[6px_6px_0px_0px_var(--border)] mb-8">
        <h3 className="text-lg font-black uppercase tracking-wider mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5" />
          {t('profile.planAndUsage', 'Plan & Usage')}
        </h3>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="border-2 border-border p-4">
            <p className="text-xs font-black uppercase tracking-wider text-muted-foreground mb-1">
              {t('profile.currentPlan', 'Plan')}
            </p>
            <p className="text-lg font-black uppercase text-primary">
              {quota?.plan ?? 'free'}
            </p>
          </div>
          <div className="border-2 border-border p-4">
            <p className="text-xs font-black uppercase tracking-wider text-muted-foreground mb-1">
              {t('profile.usageThisMonth', 'Used this month')}
            </p>
            <p className="text-lg font-black">
              {quota?.usage_count ?? 0} / {quota?.plan_limit ?? '–'}
            </p>
          </div>
        </div>

        {/* Usage bar */}
        {quota && quota.plan_limit > 0 && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-muted-foreground flex items-center gap-1">
                <BarChart3 className="w-3.5 h-3.5" />
                {t('profile.quotaUsage', 'Quota usage')}
              </span>
              <span className="text-xs font-black">{usagePercent}%</span>
            </div>
            <div className="w-full h-3 bg-muted border-2 border-border">
              <div
                className={`h-full transition-all duration-500 ${
                  usagePercent >= 90 ? 'bg-destructive' : usagePercent >= 70 ? 'bg-yellow-500' : 'bg-primary'
                }`}
                style={{ width: `${usagePercent}%` }}
              />
            </div>
            {quota.reset_at && (
              <p className="text-xs text-muted-foreground mt-1.5">
                {t('profile.resetsOn', 'Resets on')} {new Date(quota.reset_at).toLocaleDateString()}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Edit form */}
      <div className="border-4 border-border bg-card p-6 md:p-8 shadow-[6px_6px_0px_0px_var(--border)]">
        <h3 className="text-lg font-black uppercase tracking-wider mb-6 flex items-center gap-2">
          <User className="w-5 h-5" />
          {t('profile.editProfile', 'Edit Profile')}
        </h3>

        {error && (
          <div className="border-2 border-destructive bg-destructive/10 p-4 mb-6">
            <p className="text-sm font-bold text-destructive">{error}</p>
          </div>
        )}
        {success && (
          <div className="border-2 border-primary bg-primary/10 p-4 mb-6">
            <p className="text-sm font-bold text-primary">{success}</p>
          </div>
        )}

        <form onSubmit={handleSave} className="space-y-5">
          <div>
            <label htmlFor="email-display" className="block text-sm font-black uppercase tracking-wider mb-2">
              <Mail className="w-4 h-4 inline mr-1" />
              {t('auth.email', 'Email')}
            </label>
            <input
              id="email-display"
              type="email"
              value={user?.email ?? ''}
              disabled
              className="input w-full opacity-60 cursor-not-allowed"
            />
          </div>

          <div>
            <label htmlFor="display-name" className="block text-sm font-black uppercase tracking-wider mb-2">
              <User className="w-4 h-4 inline mr-1" />
              {t('profile.displayName', 'Display Name')}
            </label>
            <input
              id="display-name"
              type="text"
              maxLength={100}
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              className="input w-full"
              placeholder={t('profile.displayNamePlaceholder', 'How should we call you?')}
            />
          </div>

          <div>
            <label htmlFor="bio" className="block text-sm font-black uppercase tracking-wider mb-2">
              <FileText className="w-4 h-4 inline mr-1" />
              {t('profile.bio', 'Bio')}
            </label>
            <textarea
              id="bio"
              maxLength={300}
              rows={3}
              value={bio}
              onChange={e => setBio(e.target.value)}
              className="input w-full resize-none"
              placeholder={t('profile.bioPlaceholder', 'Tell us about yourself...')}
            />
            <p className="text-xs text-muted-foreground mt-1 text-right">{bio.length}/300</p>
          </div>

          <Button type="submit" size="lg" disabled={saving}>
            {saving ? (
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            ) : (
              <Save className="w-5 h-5 mr-2" />
            )}
            {t('profile.save', 'Save Changes')}
          </Button>
        </form>
      </div>
    </div>
  )
}
