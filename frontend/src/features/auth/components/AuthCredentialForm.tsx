import { Lock, Mail } from 'lucide-react'
import type { ReactNode } from 'react'
import type { TFunction } from 'i18next'
import type { AuthMode } from '../LoginPage'

interface AuthCredentialFormProps {
  mode: AuthMode
  email: string
  password: string
  anyLoading: boolean
  onSubmit: (event: React.FormEvent) => void
  onEmailChange: (value: string) => void
  onPasswordChange: (value: string) => void
  onForgotPassword: () => void
  t: TFunction
  children?: ReactNode
}

export function AuthCredentialForm({
  mode,
  email,
  password,
  anyLoading,
  onSubmit,
  onEmailChange,
  onPasswordChange,
  onForgotPassword,
  t,
  children,
}: AuthCredentialFormProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-5">
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
            onChange={event => onEmailChange(event.target.value)}
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
                onClick={onForgotPassword}
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
              onChange={event => onPasswordChange(event.target.value)}
              className="input w-full pl-11"
              placeholder={mode === 'register' ? t('auth.minChars', 'At least 6 characters') : '••••••••'}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              disabled={anyLoading}
            />
          </div>
        </div>
      )}

      {children}
    </form>
  )
}
