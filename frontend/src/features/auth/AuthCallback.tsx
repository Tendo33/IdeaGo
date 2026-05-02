import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { supabase } from '@/lib/supabase/client'
import { getMe } from '@/lib/api/client'
import { buildLoginRedirectTarget, normalizeAuthReturnTo } from '@/lib/auth/redirect'
import { useAuth } from '@/lib/auth/useAuth'
import { ArrowLeft, AlertTriangle, KeyRound, Loader2 } from 'lucide-react'
import { Button, buttonVariants } from '@/components/ui/Button'

type CallbackMode = 'linuxdo' | 'supabase-signin' | 'supabase-recovery'

function parseHashSearchParams(hash: string): URLSearchParams {
  return new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash)
}

function isRecoveryCallback(
  searchParams: URLSearchParams,
  hashParams: URLSearchParams,
): boolean {
  return (
    searchParams.get('type') === 'recovery' ||
    hashParams.get('type') === 'recovery' ||
    searchParams.get('flow') === 'recovery' ||
    hashParams.get('flow') === 'recovery'
  )
}

export function AuthCallback() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { applyCustomSession } = useAuth()
  const [searchParams] = useSearchParams()
  const [callbackError, setCallbackError] = useState<string | null>(null)
  const [callbackMode, setCallbackMode] = useState<CallbackMode | null>(null)
  const [timedOut, setTimedOut] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [recoveryError, setRecoveryError] = useState<string | null>(null)
  const [recoverySubmitting, setRecoverySubmitting] = useState(false)
  const authErrorParam = searchParams.get('error')
  const provider = searchParams.get('provider')?.trim().toLowerCase() ?? ''
  const returnTo = normalizeAuthReturnTo(searchParams.get('returnTo'))
  const loginHref = useMemo(() => buildLoginRedirectTarget(returnTo), [returnTo])
  const hashParams = useMemo(() => parseHashSearchParams(window.location.hash), [])
  const isLinuxDoCallback =
    provider === 'linuxdo' || authErrorParam === 'linuxdo_auth'
  const hasRecoveryHint = isRecoveryCallback(searchParams, hashParams)
  const isSupabaseCallback =
    provider === 'supabase' ||
    searchParams.has('code') ||
    hashParams.has('access_token')

  useEffect(() => {
    if (authErrorParam) return
    if (!isLinuxDoCallback) return

    let cancelled = false
    setCallbackMode('linuxdo')

    getMe({ allowUnauthorized: true })
      .then(async user => {
        if (cancelled) return
        await supabase.auth.signOut({ scope: 'local' }).catch(() => {})
        if (cancelled) return
        applyCustomSession({
          access_token: '',
          provider: 'linuxdo',
          user: {
            id: user.id,
            email: user.email ?? '',
          },
        })
        navigate(returnTo, { replace: true })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const message =
          error instanceof Error && /timed out/i.test(error.message)
            ? t('auth.callbackTimeout', 'Sign-in is taking longer than expected. Please try again.')
            : t('auth.unexpectedError', 'An unexpected error occurred')
        setCallbackError(message)
      })

    return () => {
      cancelled = true
    }
  }, [applyCustomSession, authErrorParam, isLinuxDoCallback, navigate, returnTo, t])

  const urlError = useMemo(() => {
    const errorParam = authErrorParam
    if (!errorParam) return null
    return searchParams.get('error_description') || errorParam
  }, [authErrorParam, searchParams])

  useEffect(() => {
    if (urlError || isLinuxDoCallback || !isSupabaseCallback) return

    let cancelled = false
    const timer = setTimeout(() => setTimedOut(true), 10000)
    const clearPendingTimeout = () => clearTimeout(timer)

    const enterRecoveryMode = () => {
      if (cancelled) return
      clearPendingTimeout()
      setTimedOut(false)
      setRecoveryError(null)
      setCallbackMode('supabase-recovery')
    }

    const finishSignIn = () => {
      if (cancelled) return
      clearPendingTimeout()
      setTimedOut(false)
      setCallbackMode('supabase-signin')
      navigate(returnTo, { replace: true })
    }

    void supabase.auth.getSession()
      .then(({ data: { session } }) => {
        if (cancelled) return
        if (!session?.access_token || !session.user?.id) return
        if (hasRecoveryHint) {
          enterRecoveryMode()
          return
        }
        finishSignIn()
      })
      .catch(() => {})

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY') {
        enterRecoveryMode()
        return
      }
      if (
        (event === 'SIGNED_IN' || event === 'TOKEN_REFRESHED') &&
        session?.access_token &&
        session.user?.id
      ) {
        if (hasRecoveryHint) {
          enterRecoveryMode()
          return
        }
        finishSignIn()
      }
    })

    return () => {
      cancelled = true
      subscription.unsubscribe()
      clearPendingTimeout()
    }
  }, [hasRecoveryHint, isLinuxDoCallback, isSupabaseCallback, navigate, returnTo, urlError])

  const handleRecoverySubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!newPassword) {
      setRecoveryError(
        t('auth.recoveryPasswordRequired', 'Please enter a new password.'),
      )
      return
    }
    if (newPassword.length < 6) {
      setRecoveryError(
        t(
          'auth.recoveryPasswordTooShort',
          'Password must be at least 6 characters.',
        ),
      )
      return
    }
    if (newPassword !== confirmPassword) {
      setRecoveryError(
        t('auth.recoveryPasswordMismatch', 'Passwords do not match.'),
      )
      return
    }

    setRecoveryError(null)
    setRecoverySubmitting(true)
    try {
      const { error } = await supabase.auth.updateUser({ password: newPassword })
      if (error) {
        setRecoveryError(
          error.message ||
            t('auth.unexpectedError', 'An unexpected error occurred'),
        )
        return
      }

      const { error: signOutError } = await supabase.auth.signOut({ scope: 'local' })
      if (signOutError) {
        setRecoveryError(
          signOutError.message ||
            t('auth.unexpectedError', 'An unexpected error occurred'),
        )
        return
      }

      navigate('/login', { replace: true })
    } catch {
      setRecoveryError(t('auth.unexpectedError', 'An unexpected error occurred'))
    } finally {
      setRecoverySubmitting(false)
    }
  }

  const error = urlError ?? callbackError ?? (
    timedOut ? t('auth.callbackTimeout', 'Sign-in is taking longer than expected. Please try again.') : null
  )

  if (error) {
    return (
      <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
        <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-lg text-center">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-black uppercase tracking-tight mb-3">
            {t('auth.callbackError', 'Sign-in Failed')}
          </h2>
          <p className="text-sm text-muted-foreground font-bold mb-6">{error}</p>
          <Link to={loginHref} className={buttonVariants()}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('auth.backToLogin', 'Back to login')}
          </Link>
        </div>
      </div>
    )
  }

  if (callbackMode === 'supabase-recovery') {
    return (
      <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
        <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-lg">
          <div className="flex items-center justify-center mb-4">
            <div className="flex h-12 w-12 items-center justify-center border-2 border-border bg-primary text-primary-foreground">
              <KeyRound className="h-5 w-5" />
            </div>
          </div>
          <h2 className="text-center text-xl font-black uppercase tracking-tight mb-3">
            {t('auth.resetTitle', 'Reset Password')}
          </h2>
          <p className="text-center text-sm text-muted-foreground font-bold mb-6">
            {t(
              'auth.recoverySubtitle',
              'Choose a new password to finish recovering your account.',
            )}
          </p>
          <form className="space-y-4" onSubmit={handleRecoverySubmit}>
            <div>
              <label
                htmlFor="new-password"
                className="block text-sm font-black uppercase tracking-wider mb-2"
              >
                {t('auth.newPassword', 'New password')}
              </label>
              <input
                id="new-password"
                type="password"
                minLength={6}
                value={newPassword}
                onChange={event => setNewPassword(event.target.value)}
                autoComplete="new-password"
                className="w-full border-2 border-border bg-background px-4 py-3 text-sm font-medium outline-none transition-colors focus:border-primary"
              />
            </div>
            <div>
              <label
                htmlFor="confirm-new-password"
                className="block text-sm font-black uppercase tracking-wider mb-2"
              >
                {t('auth.confirmNewPassword', 'Confirm new password')}
              </label>
              <input
                id="confirm-new-password"
                type="password"
                minLength={6}
                value={confirmPassword}
                onChange={event => setConfirmPassword(event.target.value)}
                autoComplete="new-password"
                className="w-full border-2 border-border bg-background px-4 py-3 text-sm font-medium outline-none transition-colors focus:border-primary"
              />
            </div>
            {recoveryError ? (
              <p className="text-sm font-bold text-destructive">{recoveryError}</p>
            ) : null}
            <div className="flex flex-col gap-3 pt-2">
              <Button type="submit" disabled={recoverySubmitting}>
                {recoverySubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    {t('auth.updatingPassword', 'Updating password...')}
                  </>
                ) : (
                  t('auth.updatePassword', 'Update password')
                )}
              </Button>
              <Link
                to={loginHref}
                className={buttonVariants({ variant: 'outline' })}
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                {t('auth.backToLogin', 'Back to login')}
              </Link>
            </div>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
      <div className="border-4 border-border bg-card px-12 py-8 text-center shadow-lg">
        <div className="w-8 h-8 bg-primary border-2 border-border mx-auto mb-4 animate-spin" />
        <p className="text-sm font-black uppercase tracking-widest text-muted-foreground">
          {t('auth.signingIn', 'Signing in...')}
        </p>
      </div>
    </div>
  )
}
