import { Button } from '@/components/ui/Button'
import { useEffect, useState } from 'react'
import { useNavigate, useLocation, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { supabase } from '@/lib/supabase/client'
import { useAuth } from '@/lib/auth/useAuth'
import { ArrowLeft, LogIn, UserPlus, Mail, Lock, Loader2, KeyRound } from 'lucide-react'

type AuthMode = 'login' | 'register' | 'reset'

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  )
}

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
    </svg>
  )
}

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const { user } = useAuth()
  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/'

  const [mode, setMode] = useState<AuthMode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [oauthLoading, setOauthLoading] = useState<string | null>(null)
  const [confirmSent, setConfirmSent] = useState(false)
  const [resetSent, setResetSent] = useState(false)

  useEffect(() => {
    if (user) navigate(from, { replace: true })
  }, [user, from, navigate])

  if (user) return null

  const handleOAuth = async (provider: 'github' | 'google') => {
    setError('')
    setOauthLoading(provider)
    try {
      const { error: err } = await supabase.auth.signInWithOAuth({
        provider,
        options: { redirectTo: `${window.location.origin}/auth/callback` },
      })
      if (err) setError(err.message)
    } catch {
      setError('An unexpected error occurred')
    } finally {
      setOauthLoading(null)
    }
  }

  const handleLinuxDoLogin = () => {
    setError('')
    setOauthLoading('linuxdo')
    const apiBase = import.meta.env.VITE_API_BASE_URL ?? ''
    const redirectTo = `${window.location.origin}/auth/callback`
    const query = new URLSearchParams({ redirect_to: redirectTo })
    window.location.assign(`${apiBase}/api/v1/auth/linuxdo/start?${query.toString()}`)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (mode === 'login') {
        const { error: err } = await supabase.auth.signInWithPassword({ email, password })
        if (err) {
          setError(err.message)
          return
        }
        navigate(from, { replace: true })
      } else {
        const { error: err } = await supabase.auth.signUp({ email, password })
        if (err) {
          setError(err.message)
          return
        }
        setConfirmSent(true)
      }
    } catch {
      setError('An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/login`,
      })
      if (err) {
        setError(err.message)
        return
      }
      setResetSent(true)
    } catch {
      setError('An unexpected error occurred')
    } finally {
      setLoading(false)
    }
  }

  if (resetSent) {
    return (
      <div className="app-shell px-4 min-h-[70vh] flex items-center justify-center">
        <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-[8px_8px_0px_0px_var(--border)] text-center">
          <Mail className="w-16 h-16 text-primary mx-auto mb-6" />
          <h2 className="text-2xl font-black uppercase tracking-tight mb-4">
            {t('auth.resetEmailSent', 'Check your email')}
          </h2>
          <p className="text-muted-foreground font-bold mb-8">
            {t('auth.resetEmailDesc', "We've sent a password reset link to")}
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
      <div className="app-shell px-4 min-h-[70vh] flex items-center justify-center">
        <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-[8px_8px_0px_0px_var(--border)] text-center">
          <Mail className="w-16 h-16 text-primary mx-auto mb-6" />
          <h2 className="text-2xl font-black uppercase tracking-tight mb-4">
            {t('auth.checkEmail', 'Check your email')}
          </h2>
          <p className="text-muted-foreground font-bold mb-8">
            {t('auth.confirmSent', "We've sent a confirmation link to")}
            <br />
            <span className="text-foreground">{email}</span>
          </p>
          <Button onClick={() => navigate('/login')} variant="outline">
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('auth.backToLogin', 'Back to login')}
          </Button>
        </div>
      </div>
    )
  }

  const anyLoading = loading || oauthLoading !== null

  return (
    <div className="app-shell px-4 min-h-[70vh] flex items-center justify-center">
      <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-[8px_8px_0px_0px_var(--border)]">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors mb-8"
        >
          <ArrowLeft className="w-4 h-4" />
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
              : t('auth.resetSubtitle', 'Enter your email and we\'ll send a reset link')}
        </p>

        {error && (
          <div className="border-2 border-destructive bg-destructive/10 p-4 mb-6">
            <p className="text-sm font-bold text-destructive">{error}</p>
          </div>
        )}

        {/* OAuth buttons — only on login/register */}
        {mode !== 'reset' && (
          <>
            <div className="space-y-3 mb-6">
              <button
                type="button"
                disabled={anyLoading}
                onClick={() => handleOAuth('github')}
                className="w-full inline-flex items-center justify-center gap-3 px-4 py-3 border-2 border-border bg-background font-bold text-sm uppercase tracking-wider transition-all cursor-pointer shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {oauthLoading === 'github' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <GitHubIcon className="w-5 h-5" />
                )}
                {t('auth.continueWithGithub', 'Continue with GitHub')}
              </button>
              <button
                type="button"
                disabled={anyLoading}
                onClick={() => handleOAuth('google')}
                className="w-full inline-flex items-center justify-center gap-3 px-4 py-3 border-2 border-border bg-background font-bold text-sm uppercase tracking-wider transition-all cursor-pointer shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {oauthLoading === 'google' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <GoogleIcon className="w-5 h-5" />
                )}
                {t('auth.continueWithGoogle', 'Continue with Google')}
              </button>
              <button
                type="button"
                disabled={anyLoading}
                onClick={handleLinuxDoLogin}
                className="w-full inline-flex items-center justify-center gap-3 px-4 py-3 border-2 border-border bg-background font-bold text-sm uppercase tracking-wider transition-all cursor-pointer shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {oauthLoading === 'linuxdo' ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <KeyRound className="w-5 h-5" />
                )}
                {t('auth.continueWithLinuxDo', 'Continue with LinuxDo')}
              </button>
            </div>

            <div className="flex items-center gap-4 mb-6">
              <div className="flex-1 h-0.5 bg-border" />
              <span className="text-xs font-black uppercase tracking-widest text-muted-foreground">
                {t('auth.orEmail', 'or')}
              </span>
              <div className="flex-1 h-0.5 bg-border" />
            </div>
          </>
        )}

        <form onSubmit={mode === 'reset' ? handleReset : handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="email" className="block text-sm font-black uppercase tracking-wider mb-2">
              {t('auth.email', 'Email')}
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                className="input w-full pl-11"
                placeholder="you@example.com"
                autoComplete="email"
                disabled={anyLoading}
              />
            </div>
          </div>

          {mode !== 'reset' && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label htmlFor="password" className="block text-sm font-black uppercase tracking-wider">
                  {t('auth.password', 'Password')}
                </label>
                {mode === 'login' && (
                  <button
                    type="button"
                    onClick={() => { setMode('reset'); setError('') }}
                    className="text-xs font-bold text-muted-foreground hover:text-primary transition-colors cursor-pointer"
                  >
                    {t('auth.forgotPassword', 'Forgot password?')}
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <input
                  id="password"
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="input w-full pl-11"
                  placeholder={mode === 'register' ? t('auth.minChars', 'At least 6 characters') : '••••••••'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  disabled={anyLoading}
                />
              </div>
            </div>
          )}

          <Button type="submit" className="w-full" size="lg" disabled={anyLoading}>
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
        </form>

        <div className="mt-8 pt-6 border-t-2 border-border text-center">
          {mode === 'login' ? (
            <p className="text-sm font-bold text-muted-foreground">
              {t('auth.noAccount', "Don't have an account?")}{' '}
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
              {mode === 'register' ? t('auth.hasAccount', 'Already have an account?') : t('auth.rememberPassword', 'Remember your password?')}{' '}
              <button
                type="button"
                onClick={() => { setMode('login'); setError('') }}
                className="text-primary underline underline-offset-4 hover:text-foreground transition-colors cursor-pointer"
              >
                {t('auth.signIn', 'Sign In')}
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
