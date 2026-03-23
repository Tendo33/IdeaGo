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
  getSubscriptionStatus,
  createPortalSession,
  deleteAccount,
  type QuotaInfo,
  type UserProfile,
  type SubscriptionStatus,
} from '@/lib/api/client'
import { ArrowLeft, Save, Loader2, User, Mail, FileText, Shield, BarChart3, CreditCard, Crown, ExternalLink, Trash2, AlertTriangle } from 'lucide-react'

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

export function ProfilePage() {
  const { t } = useTranslation()
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
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null)
  const [portalLoading, setPortalLoading] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [deleteError, setDeleteError] = useState('')
  const [imgError, setImgError] = useState(false)

  useEffect(() => {
    if (!user) return
    let cancelled = false

    async function load() {
      const [profileResult, quotaResult, subResult] = await Promise.allSettled([
        getMyProfile(),
        getQuotaInfo(),
        getSubscriptionStatus(),
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

      if (subResult.status === 'fulfilled') {
        setSubscription(subResult.value)
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
    ? new Date(profile.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long' })
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

      {/* Plan & usage card */}
      <div className="border-4 border-border bg-card p-6 md:p-8 shadow-md hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-lg transition-all duration-300 mb-8">
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
                  usagePercent >= 90 ? 'bg-destructive' : usagePercent >= 70 ? 'bg-warning' : 'bg-primary'
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

      {/* Subscription management */}
      {subscription?.stripe_configured && (
        <div className="border-4 border-border bg-card p-6 md:p-8 shadow-md hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-lg transition-all duration-300 mb-8">
          <h3 className="text-lg font-black uppercase tracking-wider mb-4 flex items-center gap-2">
            <CreditCard className="w-5 h-5" />
            {t('profile.subscription', 'Subscription')}
          </h3>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              {subscription.plan === 'pro' ? (
                <Crown className="w-6 h-6 text-primary" />
              ) : null}
              <div>
                <p className="font-black uppercase text-lg">
                  {subscription.plan === 'pro'
                    ? t('profile.proPlan', 'Pro Plan')
                    : t('profile.freePlan', 'Free Plan')}
                </p>
                <p className="text-sm text-muted-foreground font-bold">
                  {subscription.has_subscription
                    ? t('profile.activeSubscription', 'Active subscription')
                    : t('profile.noSubscription', 'No active subscription')}
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            {subscription.has_subscription ? (
              <Button
                variant="outline"
                disabled={portalLoading}
                onClick={async () => {
                  setPortalLoading(true)
                  try {
                    const url = await createPortalSession(window.location.href)
                    window.location.href = url
                  } catch {
                    setPortalLoading(false)
                  }
                }}
              >
                {portalLoading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <ExternalLink className="w-4 h-4 mr-2" />
                )}
                {t('profile.manageSubscription', 'Manage Subscription')}
              </Button>
            ) : (
              <Link
                to="/pricing"
                className="inline-flex items-center justify-center gap-2 min-h-[44px] border-2 border-border bg-primary text-primary-foreground px-4 py-2 text-sm font-bold uppercase tracking-wider shadow transition-all hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-none"
              >
                <Crown className="w-4 h-4" />
                {t('profile.upgradeToPro', 'Upgrade to Pro')}
              </Link>
            )}
          </div>
        </div>
      )}

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
