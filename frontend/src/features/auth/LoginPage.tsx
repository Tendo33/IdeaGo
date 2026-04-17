import { Button } from '@/components/ui/Button'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { supabase } from '@/lib/supabase/client'
import { useAuth } from '@/lib/auth/useAuth'
import {
  DEFAULT_AUTH_RETURN_TO,
  buildAuthCallbackUrl,
  buildLoginRedirectTarget,
  buildReturnToFromLocation,
  normalizeAuthReturnTo,
} from '@/lib/auth/redirect'
import { startLinuxDoAuth } from '@/lib/api/client'
import { ArrowLeft, LogIn, UserPlus, Mail, Loader2, KeyRound } from 'lucide-react'
import {
  TurnstilePanel,
  type TurnstileStatus,
  type TurnstileTheme,
} from './components/TurnstilePanel'
import { AuthProviderButtons } from './components/AuthProviderButtons'
import { AuthCredentialForm } from './components/AuthCredentialForm'
import { getTurnstileMessage } from './components/turnstileUtils'

import { useDocumentTitle } from '@/hooks/useDocumentTitle'

export type AuthMode = 'login' | 'register' | 'reset'

export function LoginPage() {
  const { t, i18n } = useTranslation()
  useDocumentTitle(t('auth.loginTitle', 'Sign In') + ' — IdeaGo')

  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const stateFrom = (location.state as {
    from?: { pathname?: string; search?: string; hash?: string }
  } | null)?.from
  const searchParams = new URLSearchParams(location.search)
  const from = normalizeAuthReturnTo(
    searchParams.get('returnTo') ?? buildReturnToFromLocation(stateFrom),
  )

  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [oauthLoading, setOauthLoading] = useState<string | null>(null)
  const [confirmSent, setConfirmSent] = useState(false)
  const [resetSent, setResetSent] = useState(false)
  const [captchaToken, setCaptchaToken] = useState<string | null>(null)
  const [captchaStatus, setCaptchaStatus] = useState<TurnstileStatus>('verifying')
  const [turnstileTheme, setTurnstileTheme] = useState<TurnstileTheme>(() =>
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark')
      ? 'dark'
      : 'light',
  )
  const turnstileSiteKey = import.meta.env.VITE_TURNSTILE_SITE_KEY?.trim() ?? ''
  const emailLanguage = (i18n.resolvedLanguage ?? i18n.language ?? 'en').toLowerCase().startsWith('zh') ? 'zh' : 'en'
  const authBlocked = !turnstileSiteKey || captchaStatus !== 'success' || !captchaToken

  const resetCaptcha = useCallback(() => {
    setCaptchaToken(null)
    setCaptchaStatus(turnstileSiteKey ? 'verifying' : 'unsupported')
  }, [turnstileSiteKey])
  const authCallbackUrl = buildAuthCallbackUrl(window.location.origin, 'supabase', from)
  const loginHref = buildLoginRedirectTarget(from)
  const linuxDoCallbackUrl = buildAuthCallbackUrl(window.location.origin, 'linuxdo', from)
  const passwordResetCallbackUrl = buildAuthCallbackUrl(
    window.location.origin,
    'supabase',
    DEFAULT_AUTH_RETURN_TO,
  ) + '&type=recovery'

  useEffect(() => {
    if (user) navigate(from, { replace: true })
  }, [user, from, navigate])

  useEffect(() => {
    if (!turnstileSiteKey) {
      setCaptchaToken(null)
      setCaptchaStatus('unsupported')
    }
  }, [turnstileSiteKey])

  useEffect(() => {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    const syncTheme = () => {
      setTurnstileTheme(root.classList.contains('dark') ? 'dark' : 'light')
    }

    syncTheme()
    const observer = new MutationObserver(syncTheme)
    observer.observe(root, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])

  if (user) return null

  const requireCaptcha = () => {
    if (!turnstileSiteKey) {
      setError(
        t(
          'auth.turnstileConfigMissing',
          'Human verification is not configured yet. Please contact support.',
        ),
      )
      return null
    }
    if (captchaStatus !== 'success' || !captchaToken) {
      setError(getTurnstileMessage(t, captchaStatus))
      return null
    }
    return captchaToken
  }

  const handleOAuth = async (provider: 'github' | 'google') => {
    setError('')
    setOauthLoading(provider)
    try {
      const { error: err } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: authCallbackUrl },
      })
      if (err) {
        setError(err.message)
        return
      }
    } catch {
      setError(t('auth.unexpectedError'))
    } finally {
      setOauthLoading(null)
    }
  }

  const handleLinuxDoLogin = async () => {
    setError('')
    const nextCaptchaToken = requireCaptcha()
    if (!nextCaptchaToken) {
      return
    }
    setOauthLoading('linuxdo')
    try {
      const redirectUrl = await startLinuxDoAuth({
        redirectTo: linuxDoCallbackUrl,
        captchaToken: nextCaptchaToken,
      })
      resetCaptcha()
      window.location.assign(redirectUrl)
    } catch (err) {
      resetCaptcha()
      setError(err instanceof Error ? err.message : t('auth.unexpectedError'))
    } finally {
      setOauthLoading(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (mode === 'login') {
        const nextCaptchaToken = requireCaptcha()
        if (!nextCaptchaToken) {
          return
        }
        let err: { message: string } | null = null
        try {
          const result = await supabase.auth.signInWithPassword({
            email,
            password,
            options: {
              captchaToken: nextCaptchaToken,
            },
          })
          err = result.error
        } finally {
          resetCaptcha()
        }
        if (err) {
          setError(err.message)
          return
        }
        navigate(from, { replace: true })
      } else {
        const nextCaptchaToken = requireCaptcha()
        if (!nextCaptchaToken) {
          return
        }
        let err: { message: string } | null = null
        let activeSession = false
        try {
          const result = await supabase.auth.signUp({
            email,
            password,
            options: {
              captchaToken: nextCaptchaToken,
              emailRedirectTo: authCallbackUrl,
              data: {
                language: emailLanguage,
              },
            },
          })
          err = result.error
          activeSession = Boolean(
            result.data?.session?.access_token && result.data.session.user?.id,
          )
        } finally {
          resetCaptcha()
        }
        if (err) {
          setError(err.message)
          return
        }
        if (activeSession) {
          navigate(from, { replace: true })
          return
        }
        setConfirmSent(true)
      }
    } catch {
      setError(t('auth.unexpectedError'))
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const nextCaptchaToken = requireCaptcha()
      if (!nextCaptchaToken) {
        return
      }
      const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: passwordResetCallbackUrl,
        captchaToken: nextCaptchaToken,
      })
      if (err) {
        setError(err.message)
        return
      }
      setResetSent(true)
    } catch {
      setError(t('auth.unexpectedError'))
    } finally {
      resetCaptcha()
      setLoading(false)
    }
  }

  if (resetSent) {
    return (
      <div className="app-shell px-4 py-12 md:py-24 min-h-[85vh] flex items-center justify-center">
        <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-lg text-center">
          <Mail className="w-16 h-16 text-primary mx-auto mb-6" />
          <h2 className="text-2xl font-black uppercase tracking-tight mb-4">
            {t('auth.resetEmailSent', 'Check your email')}
          </h2>
          <p className="text-muted-foreground font-bold mb-8">
            {t('auth.resetEmailDesc')}
            <br />
            <span className="text-foreground">{email}</span>
          </p>
          <Button onClick={() => { setMode('login'); setResetSent(false); setError('') }} variant="outline">
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('auth.backToLogin', 'Back to login')}
          </Button>
        </div>
      </div>
    )
  }

  if (confirmSent) {
    return (
      <div className="app-shell px-4 py-12 md:py-24 min-h-[85vh] flex items-center justify-center">
        <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-lg text-center">
          <Mail className="w-16 h-16 text-primary mx-auto mb-6" />
          <h2 className="text-2xl font-black uppercase tracking-tight mb-4">
            {t('auth.checkEmail', 'Check your email')}
          </h2>
          <p className="text-muted-foreground font-bold mb-8">
            {t('auth.confirmSent')}
            <br />
            <span className="text-foreground">{email}</span>
          </p>
          <Button onClick={() => navigate(loginHref)} variant="outline">
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('auth.backToLogin', 'Back to login')}
          </Button>
        </div>
      </div>
    )
  }

  const anyLoading = loading || oauthLoading !== null

  return (
    <div className="app-shell px-4 py-12 md:py-24 min-h-[85vh] flex items-center justify-center">
      <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-lg">
        <Link
          to="/"
          className="topbar-action mb-8"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('nav.home', 'Home')}
        </Link>

        <h1 className="text-3xl md:text-4xl font-black uppercase tracking-tight mb-2">
          {mode === 'login'
            ? t('auth.loginTitle', 'Sign In')
            : mode === 'register'
              ? t('auth.registerTitle', 'Create Account')
              : t('auth.resetTitle', 'Reset Password')}
        </h1>
        <p className="text-muted-foreground font-bold mb-8">
          {mode === 'login'
            ? t('auth.loginSubtitle', 'Sign in to access your reports')
            : mode === 'register'
              ? t('auth.registerSubtitle', 'Start analyzing competitors today')
              : t('auth.resetSubtitle')}
        </p>

        {error && (
          <div className="border-2 border-destructive bg-destructive/10 p-4 mb-6">
            <p className="text-sm font-bold text-destructive">{error}</p>
          </div>
        )}

        {/* OAuth buttons — only on login/register */}
        {mode !== 'reset' && (
          <>
            <AuthProviderButtons
              anyLoading={anyLoading}
              oauthLoading={oauthLoading}
              onGithub={() => handleOAuth('github')}
              onGoogle={() => handleOAuth('google')}
              onLinuxDo={handleLinuxDoLogin}
              t={t}
            />

            <div className="flex items-center gap-4 mb-6">
              <div className="flex-1 h-0.5 bg-border" />
              <span className="text-xs font-black uppercase tracking-widest text-muted-foreground">
                {t('auth.orEmail', 'or')}
              </span>
              <div className="flex-1 h-0.5 bg-border" />
            </div>
          </>
        )}

        <AuthCredentialForm
          mode={mode}
          email={email}
          password={password}
          anyLoading={anyLoading}
          onSubmit={mode === 'reset' ? handleReset : handleSubmit}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          onForgotPassword={() => { setMode('reset'); setError('') }}
          t={t}
        >
          <TurnstilePanel
            siteKey={turnstileSiteKey}
            status={captchaStatus}
            theme={turnstileTheme}
            onTokenChange={setCaptchaToken}
            onStatusChange={setCaptchaStatus}
            t={t}
          />

          <Button
            type="submit"
            className="w-full"
            size="lg"
            disabled={anyLoading || authBlocked}
          >
            {loading ? (
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
            ) : mode === 'login' ? (
              <LogIn className="w-5 h-5 mr-2" />
            ) : mode === 'register' ? (
              <UserPlus className="w-5 h-5 mr-2" />
            ) : (
              <KeyRound className="w-5 h-5 mr-2" />
            )}
            {mode === 'login'
              ? t('auth.signIn', 'Sign In')
              : mode === 'register'
                ? t('auth.signUp', 'Sign Up')
                : t('auth.sendResetLink', 'Send Reset Link')}
          </Button>
        </AuthCredentialForm>

        <div className="mt-8 pt-6 border-t-2 border-border text-center">
          {mode === 'login' ? (
            <p className="text-sm font-bold text-muted-foreground">
              {t('auth.noAccount')}{' '}
              <button
                type="button"
                onClick={() => { setMode('register'); setError('') }}
                className="text-primary underline underline-offset-4 hover:text-foreground transition-colors cursor-pointer"
              >
                {t('auth.signUp', 'Sign Up')}
              </button>
            </p>
          ) : (
            <p className="text-sm font-bold text-muted-foreground">
              {mode === 'register' ? t('auth.hasAccount') : t('auth.rememberPassword')}{' '}
              <button
                type="button"
                onClick={() => { setMode('login'); setError('') }}
                className="text-primary underline underline-offset-4 hover:text-foreground transition-colors cursor-pointer"
              >
                {t('auth.signIn', 'Sign In')}
              </button>
            </p>
          )}

          <p className="mt-4 text-xs text-muted-foreground/70">
            {t('auth.legalNotice', 'By continuing, you agree to our')}{' '}
            <Link to="/terms" className="underline underline-offset-2 hover:text-foreground transition-colors">
              {t('legal.termsTitle', 'Terms of Service')}
            </Link>{' '}
            {t('common.and', 'and')}{' '}
            <Link to="/privacy" className="underline underline-offset-2 hover:text-foreground transition-colors">
              {t('legal.privacyTitle', 'Privacy Policy')}
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
