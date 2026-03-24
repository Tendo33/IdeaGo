import { Button, buttonVariants } from '@/components/ui/Button'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { useAuth } from '@/lib/auth/useAuth'
import {
  getMyProfile,
  getQuotaInfo,
  updateMyProfile,
  deleteAccount,
  type QuotaInfo,
  type UserProfile,
} from '@/lib/api/client'
import { ArrowLeft, Save, Loader2, User, Mail, FileText, Shield, BarChart3, Trash2, AlertTriangle } from 'lucide-react'
import { formatAppDate, formatAppDateTime } from '@/lib/utils/dateLocale'

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

export function ProfilePage() {
  const { t, i18n } = useTranslation()
  const language = i18n.resolvedLanguage ?? i18n.language
  useDocumentTitle(t('profile.title', 'Profile') + ' — IdeaGo')
  const { user, signOut } = useAuth()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [quota, setQuota] = useState<QuotaInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const [displayName, setDisplayName] = useState('')
  const [bio, setBio] = useState('')
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [imgError, setImgError] = useState(false)

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
  }, [user, t])

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
      toast.success(t('profile.saved', 'Profile updated successfully'))
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      const message = err instanceof Error ? err.message : t('profile.updateError')
      setError(message)
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="app-shell pt-16 flex items-center justify-center">
        <div className="border-4 border-border bg-card px-12 py-8 text-center shadow-lg">
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
    ? formatAppDate(profile.created_at, language, { year: 'numeric', month: 'long' })
    : ''

  const usagePercent = quota && quota.plan_limit > 0
    ? Math.min(100, Math.round((quota.usage_count / quota.plan_limit) * 100))
    : 0

  return (
    <div className="app-shell max-w-3xl pt-8 pb-16">
      <Link
        to="/"
        className={buttonVariants({ variant: 'secondary', size: 'sm', className: "mb-8 bg-card" })}
      >
        <ArrowLeft className="w-4 h-4 mr-2" />
        {t('nav.home', 'Home')}
      </Link>

      <div className="border-4 border-border bg-card p-6 md:p-10 mb-8 shadow-lg flex items-center justify-between">
        <h1 className="text-4xl md:text-5xl font-black uppercase tracking-tighter">
          {t('profile.title', 'Profile')}
        </h1>
        <div className="hidden sm:block w-16 h-16 bg-primary border-4 border-border shadow-sm transform rotate-12"></div>
      </div>

      {/* Avatar + info header */}
        <div className="border-4 border-border bg-card p-6 md:p-8 shadow-md hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-lg transition-all duration-300 mb-8">
          <div className="flex items-center gap-6">
          {profile?.avatar_url && !imgError ? (
            <img
              src={profile.avatar_url}
              alt=""
              onError={() => setImgError(true)}
              className="w-20 h-20 shrink-0 border-4 border-border object-cover"
              loading="lazy"
              width={80}
              height={80}
            />
          ) : (
            <div className="w-20 h-20 shrink-0 bg-primary text-primary-foreground border-4 border-border flex items-center justify-center text-3xl font-black">
              {avatarInitial}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <h2 className="text-xl font-black truncate" title={displayName || user?.email || 'User'}>
              {displayName || user?.email || 'User'}
            </h2>
            <p className="text-sm text-muted-foreground font-bold truncate" title={user?.email}>{user?.email}</p>
            {memberSince && (
              <p className="text-xs text-muted-foreground mt-1">
                {t('profile.memberSince', 'Member since')} {memberSince}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Daily usage card */}
      <div className="border-4 border-border bg-card p-6 md:p-8 shadow-md hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-lg transition-all duration-300 mb-8">
        <h3 className="text-lg font-black uppercase tracking-wider mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5" />
          {t('profile.planAndUsage', 'Daily Usage')}
        </h3>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="border-2 border-border p-4">
            <p className="text-xs font-black uppercase tracking-wider text-muted-foreground mb-1">
              {t('profile.currentPlan', 'Quota type')}
            </p>
            <p className="text-lg font-black uppercase text-primary">
              {t('profile.dailyQuotaLabel', 'Daily limit')}
            </p>
          </div>
          <div className="border-2 border-border p-4">
            <p className="text-xs font-black uppercase tracking-wider text-muted-foreground mb-1">
              {t('profile.usageThisMonth', 'Used today')}
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
                  usagePercent >= 90 ? 'bg-destructive' : usagePercent >= 70 ? 'bg-warning' : 'bg-primary'
                }`}
                style={{ width: `${usagePercent}%` }}
              />
            </div>
            {quota.reset_at && (
              <p className="text-xs text-muted-foreground mt-1.5">
                {t('profile.resetsOn', 'Resets on')} {formatAppDateTime(quota.reset_at, language)}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Edit form */}
      <div className="border-4 border-border bg-card p-6 md:p-8 shadow-md hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-lg transition-all duration-300">
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
              aria-describedby="bio-count"
            />
            <p id="bio-count" className="text-xs text-muted-foreground mt-1 text-right">{bio.length}/300</p>
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

      {/* Danger zone */}
      <div className="border-4 border-destructive bg-destructive/5 p-6 md:p-8 shadow-md shadow-destructive mt-8 hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-lg hover:shadow-destructive transition-all duration-300">
        <h3 className="text-lg font-black uppercase tracking-wider mb-4 flex items-center gap-2 text-destructive">
          <AlertTriangle className="w-5 h-5" />
          {t('profile.dangerZone', 'Danger Zone')}
        </h3>
        <p className="text-sm font-bold text-muted-foreground mb-4">
          {t('profile.deleteWarning', 'Permanently delete your account and all associated data. This action cannot be undone.')}
        </p>
        {deleteError && (
          <div className="border-2 border-destructive bg-destructive/10 p-3 mb-4">
            <p className="text-sm font-bold text-destructive">{deleteError}</p>
          </div>
        )}
        {!deleteConfirmOpen ? (
          <Button
            variant="destructive"
            onClick={() => setDeleteConfirmOpen(true)}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            {t('profile.deleteAccount', 'Delete Account')}
          </Button>
        ) : (
          <div className="border-2 border-destructive p-4 space-y-4">
            <p className="text-sm font-black text-destructive">
              {t('profile.deleteConfirm', 'Are you sure? All reports, profile data, and subscription will be permanently removed.')}
            </p>
            <div className="flex gap-3">
              <Button
                variant="destructive"
                disabled={deleteLoading}
                onClick={async () => {
                  setDeleteLoading(true)
                  setDeleteError('')
                  try {
                    await deleteAccount()
                    signOut()
                    window.location.href = '/'
                  } catch (err) {
                    setDeleteError(
                      err instanceof Error ? err.message : t('profile.deleteError', 'Failed to delete account')
                    )
                    setDeleteLoading(false)
                  }
                }}
              >
                {deleteLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4 mr-2" />
                )}
                {t('profile.confirmDelete', 'Yes, Delete Everything')}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setDeleteConfirmOpen(false)
                  setDeleteError('')
                }}
              >
                {t('profile.cancelDelete', 'Cancel')}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
