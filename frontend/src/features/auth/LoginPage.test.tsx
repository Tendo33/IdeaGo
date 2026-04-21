import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { useContext, useState } from 'react'
import { LoginPage } from './LoginPage'
import { AuthCallback } from './AuthCallback'
import { AuthContext } from '@/lib/auth/AuthContext'
import { AuthProvider } from '@/lib/auth/AuthProvider'

const navigateMock = vi.fn()
const signUpMock = vi.fn()
const signInWithPasswordMock = vi.fn()
const signInWithOAuthMock = vi.fn()
const resetPasswordForEmailMock = vi.fn()
const supabaseSignOutMock = vi.fn()
const updateUserMock = vi.fn()
const onAuthStateChangeMock = vi.fn()
const applyCustomSessionMock = vi.fn()
const getMyProfileMock = vi.fn()
const getMeMock = vi.fn()
const getSessionMock = vi.fn()
const startLinuxDoAuthMock = vi.fn()
const logoutAuthSessionMock = vi.fn()
const turnstileRenderMock = vi.fn()
const turnstileResetMock = vi.fn()
const turnstileRemoveMock = vi.fn()
const clearHistoryCacheMock = vi.fn()

type TurnstileRenderOptions = {
  callback?: (token: string) => void
  'expired-callback'?: () => void
  'error-callback'?: () => void
  theme?: 'light' | 'dark' | 'auto'
}

let authUser: { id: string; email: string } | null = null
let currentLanguage = 'zh-CN'
let latestTurnstileOptions: TurnstileRenderOptions | null = null
let authStateChangeCallback:
  | ((event: string, session: { access_token: string; user: { id: string; email?: string } } | null) => void)
  | null = null

function installTurnstileMock() {
  turnstileRenderMock.mockImplementation(
    (_element: string | HTMLElement, options: TurnstileRenderOptions) => {
      latestTurnstileOptions = options
      return 'widget-1'
    },
  )
  Object.defineProperty(window, 'turnstile', {
    configurable: true,
    writable: true,
    value: {
      render: turnstileRenderMock,
      reset: turnstileResetMock,
      remove: turnstileRemoveMock,
    },
  })
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key,
    i18n: {
      language: currentLanguage,
      resolvedLanguage: currentLanguage,
    },
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

vi.mock('@/hooks/useDocumentTitle', () => ({
  useDocumentTitle: vi.fn(),
}))

vi.mock('@/lib/auth/useAuth', () => ({
  useAuth: () => ({
    user: authUser,
    applyCustomSession: (...args: unknown[]) => applyCustomSessionMock(...args),
  }),
}))

vi.mock('@/lib/auth/token', () => ({
  saveCustomAuthSession: vi.fn(),
  setAccessToken: vi.fn(),
  readCustomAuthSession: vi.fn(() => null),
  clearCustomAuthSession: vi.fn(),
}))

vi.mock('@/lib/supabase/client', () => ({
  supabase: {
    auth: {
      signInWithOAuth: (...args: unknown[]) => signInWithOAuthMock(...args),
      signInWithPassword: (...args: unknown[]) => signInWithPasswordMock(...args),
      signUp: (...args: unknown[]) => signUpMock(...args),
      resetPasswordForEmail: (...args: unknown[]) => resetPasswordForEmailMock(...args),
      signOut: (...args: unknown[]) => supabaseSignOutMock(...args),
      updateUser: (...args: unknown[]) => updateUserMock(...args),
      getSession: (...args: unknown[]) => getSessionMock(...args),
      onAuthStateChange: (...args: unknown[]) => onAuthStateChangeMock(...args),
    },
  },
}))

vi.mock('@/lib/api/client', () => ({
  getMyProfile: (...args: unknown[]) => getMyProfileMock(...args),
  getMe: (...args: unknown[]) => getMeMock(...args),
  startLinuxDoAuth: (...args: unknown[]) => startLinuxDoAuthMock(...args),
  logoutAuthSession: (...args: unknown[]) => logoutAuthSessionMock(...args),
}))

vi.mock('@/features/history/historyCache', () => ({
  clearHistoryCache: () => clearHistoryCacheMock(),
}))

function AuthStateProbe() {
  const auth = useContext(AuthContext)
  const user = auth?.user ?? null
  const loading = auth?.loading ?? true
  return <div>{loading ? 'loading' : (user?.id ?? 'anonymous')}</div>
}

function AuthSignOutProbe() {
  const auth = useContext(AuthContext)
  const [error, setError] = useState('')
  const user = auth?.user ?? null
  const loading = auth?.loading ?? true

  return (
    <div>
      <div>{loading ? 'loading' : (user?.id ?? 'anonymous')}</div>
      <div>{error}</div>
      <button
        type="button"
        onClick={() => {
          void auth?.signOut().catch(err => {
            setError(err instanceof Error ? err.message : 'logout failed')
          })
        }}
      >
        sign-out
      </button>
    </div>
  )
}

describe('LoginPage registration locale metadata', () => {
  beforeEach(() => {
    authUser = null
    currentLanguage = 'zh-CN'
    latestTurnstileOptions = null
    authStateChangeCallback = null
    navigateMock.mockReset()
    signUpMock.mockReset()
    signInWithPasswordMock.mockReset()
    signInWithOAuthMock.mockReset()
    resetPasswordForEmailMock.mockReset()
    supabaseSignOutMock.mockReset()
    updateUserMock.mockReset()
    onAuthStateChangeMock.mockReset()
    applyCustomSessionMock.mockReset()
    getMyProfileMock.mockReset()
    getMeMock.mockReset()
    getSessionMock.mockReset()
    startLinuxDoAuthMock.mockReset()
    logoutAuthSessionMock.mockReset()
    turnstileRenderMock.mockReset()
    turnstileResetMock.mockReset()
    turnstileRemoveMock.mockReset()
    clearHistoryCacheMock.mockReset()
    vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key')
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:3000')
    installTurnstileMock()
    signUpMock.mockResolvedValue({ data: { session: null }, error: null })
    signInWithPasswordMock.mockResolvedValue({ error: null })
    resetPasswordForEmailMock.mockResolvedValue({ error: null })
    signInWithOAuthMock.mockResolvedValue({ data: { provider: 'google', url: 'https://oauth.example.com' }, error: null })
    supabaseSignOutMock.mockResolvedValue({ error: null })
    updateUserMock.mockResolvedValue({ data: { user: { id: 'user-123' } }, error: null })
    startLinuxDoAuthMock.mockResolvedValue('https://linux.do/oauth2/authorize?state=test')
    logoutAuthSessionMock.mockResolvedValue(undefined)
    getSessionMock.mockResolvedValue({ data: { session: null } })
    onAuthStateChangeMock.mockImplementation((callback?: typeof authStateChangeCallback) => {
      authStateChangeCallback = callback ?? null
      return ({
      data: {
        subscription: {
          unsubscribe: vi.fn(),
        },
      },
      })
    })
    document.documentElement.classList.remove('dark')
    window.history.replaceState({}, '', '/login')
    window.location.hash = ''
    localStorage.clear()
  })

  it('renders turnstile in login mode and blocks auth actions until verified', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('Human verification')).toBeInTheDocument()
    expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)
    expect(turnstileRenderMock).toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Sign In' })[0])

    await waitFor(() => {
      expect(signInWithPasswordMock).not.toHaveBeenCalled()
    })
    expect(screen.getByText('Verifying you are human...')).toBeInTheDocument()
  })

  it('passes dark theme to turnstile when app is in dark mode', async () => {
    document.documentElement.classList.add('dark')

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    await screen.findByText('Human verification')

    expect(latestTurnstileOptions?.theme).toBe('dark')
    document.documentElement.classList.remove('dark')
  })

  it('reuses captcha verification when switching from login to register', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    await screen.findByText('Human verification')
    act(() => {
      latestTurnstileOptions?.callback?.('turnstile-token')
    })

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: 'Sign In' })[0]).toBeEnabled()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }))

    expect(turnstileRenderMock).toHaveBeenCalledTimes(1)
    expect(screen.getAllByRole('button', { name: 'Sign Up' })[0]).toBeEnabled()
  })

  it('passes captchaToken and the current UI language to Supabase signUp metadata', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }))
    act(() => {
      latestTurnstileOptions?.callback?.('turnstile-token')
    })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Sign Up' })[0])

    await waitFor(() => {
      expect(signUpMock).toHaveBeenCalledWith({
        email: 'user@example.com',
        password: 'password123',
        options: {
          captchaToken: 'turnstile-token',
          emailRedirectTo: expect.stringContaining(
            '/auth/callback?provider=supabase&returnTo=%2F',
          ),
          data: {
            language: 'zh',
          },
        },
      })
    })
  })

  it('navigates to returnTo immediately when email sign up returns an active session', async () => {
    signUpMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'supabase-token',
          user: { id: 'supabase-user', email: 'user@example.com' },
        },
      },
      error: null,
    })

    render(
      <MemoryRouter initialEntries={['/login?returnTo=%2Freports%2Fr-1']}>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }))
    act(() => {
      latestTurnstileOptions?.callback?.('turnstile-token')
    })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Sign Up' })[0])

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith('/reports/r-1', { replace: true })
    })
    expect(screen.queryByText('Check your email')).not.toBeInTheDocument()
  })

  it('preserves returnTo when leaving the registration confirmation screen', async () => {
    render(
      <MemoryRouter initialEntries={['/login?returnTo=%2Freports%2Fr-1%3Ftab%3Dsummary']}>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }))
    act(() => {
      latestTurnstileOptions?.callback?.('turnstile-token')
    })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Sign Up' })[0])

    expect(await screen.findByText('Check your email')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Back to login' }))

    expect(navigateMock).toHaveBeenCalledWith(
      '/login?returnTo=%2Freports%2Fr-1%3Ftab%3Dsummary',
    )
  })

  it('blocks registration again when the captcha expires', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    act(() => {
      latestTurnstileOptions?.callback?.('turnstile-token')
    })

    act(() => {
      latestTurnstileOptions?.['expired-callback']?.()
    })

    await waitFor(() => {
      expect(screen.getByText('Verification expired. Please wait for a new check.')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }))
    expect(screen.getAllByRole('button', { name: 'Sign Up' })[0]).toBeDisabled()
    expect(turnstileResetMock).toHaveBeenCalled()
  })

  it('passes captchaToken to password login', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    act(() => {
      latestTurnstileOptions?.callback?.('turnstile-token')
    })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Sign In' })[0])

    await waitFor(() => {
      expect(signInWithPasswordMock).toHaveBeenCalledWith({
        email: 'user@example.com',
        password: 'password123',
        options: {
          captchaToken: 'turnstile-token',
        },
      })
    })
  })

  it('clears captcha after a failed password login attempt', async () => {
    signInWithPasswordMock.mockResolvedValueOnce({ error: { message: 'Invalid login credentials' } })

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    act(() => {
      latestTurnstileOptions?.callback?.('turnstile-token')
    })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'wrong-password' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Sign In' })[0])

    expect(await screen.findByText('Invalid login credentials')).toBeInTheDocument()

    expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)
  })

  it('clears captcha after a failed sign up attempt', async () => {
    signUpMock.mockResolvedValueOnce({ error: { message: 'User already registered' } })

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }))
    act(() => {
      latestTurnstileOptions?.callback?.('turnstile-token')
    })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Sign Up' })[0])

    expect(await screen.findByText('User already registered')).toBeInTheDocument()

    expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)
  })

  it('allows Supabase social sign-in without requiring local turnstile and still requires it for LinuxDo', async () => {
    const assignMock = vi.fn()
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        origin: 'https://ideago.simonsun.cc',
        assign: assignMock,
      },
    })

    try {
      render(
        <MemoryRouter
          initialEntries={[{
            pathname: '/login',
            search: '?returnTo=%2Freports%2Fr-1%3Ftab%3Dsummary',
          }]}
        >
          <LoginPage />
        </MemoryRouter>,
      )

      fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
      await waitFor(() => {
        expect(signInWithOAuthMock).toHaveBeenCalledWith({
          provider: 'google',
          options: { redirectTo: 'https://ideago.simonsun.cc/auth/callback?provider=supabase&returnTo=%2Freports%2Fr-1%3Ftab%3Dsummary' },
        })
      })

      fireEvent.click(screen.getByRole('button', { name: 'Continue with LinuxDo' }))
      expect(startLinuxDoAuthMock).not.toHaveBeenCalled()
      expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)

      act(() => {
        latestTurnstileOptions?.callback?.('linuxdo-token')
      })
      fireEvent.click(screen.getByRole('button', { name: 'Continue with LinuxDo' }))

      await waitFor(() => {
        expect(startLinuxDoAuthMock).toHaveBeenCalledWith({
          redirectTo: 'https://ideago.simonsun.cc/auth/callback?provider=linuxdo&returnTo=%2Freports%2Fr-1%3Ftab%3Dsummary',
          captchaToken: 'linuxdo-token',
        })
      })
      expect(assignMock).toHaveBeenCalledWith('https://linux.do/oauth2/authorize?state=test')
    } finally {
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: originalLocation,
      })
    }
  })

  it('keeps LinuxDo captcha errors inside the auth page', async () => {
    const assignMock = vi.fn()
    const originalLocation = window.location
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...originalLocation,
        origin: 'https://ideago.simonsun.cc',
        assign: assignMock,
      },
    })
    startLinuxDoAuthMock.mockRejectedValueOnce(new Error('LinuxDo login failed: Invalid captcha token'))

    try {
      render(
        <MemoryRouter initialEntries={['/login']}>
          <LoginPage />
        </MemoryRouter>,
      )

      act(() => {
        latestTurnstileOptions?.callback?.('linuxdo-token')
      })
      fireEvent.click(screen.getByRole('button', { name: 'Continue with LinuxDo' }))

      expect(await screen.findByText('LinuxDo login failed: Invalid captcha token')).toBeInTheDocument()
      expect(assignMock).not.toHaveBeenCalled()
      expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)
    } finally {
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: originalLocation,
      })
    }
  })

  it('passes captchaToken to password reset requests', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Forgot password?' }))
    act(() => {
      latestTurnstileOptions?.callback?.('reset-token')
    })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send Reset Link' }))

    await waitFor(() => {
      expect(resetPasswordForEmailMock).toHaveBeenCalledWith(
        'user@example.com',
        expect.objectContaining({
          redirectTo: expect.stringContaining('/auth/callback?provider=supabase&returnTo=%2F&type=recovery'),
          captchaToken: 'reset-token',
        }),
      )
    })
  })

  it('resets captcha when password reset throws before returning a response', async () => {
    resetPasswordForEmailMock.mockRejectedValueOnce(new Error('network down'))

    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Forgot password?' }))
    act(() => {
      latestTurnstileOptions?.callback?.('reset-token')
    })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'user@example.com' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Send Reset Link' }))

    expect(
      await screen.findByText(/auth\.unexpectedError|An unexpected error occurred/),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)
  })

  it('verifies LinuxDo callback session via backend and redirects to returnTo immediately', async () => {
    getMeMock.mockResolvedValue({ id: 'user-123', email: 'linuxdo@example.com' })
    window.history.replaceState({}, '', '/auth/callback?provider=linuxdo&returnTo=%2Freports%2Fr-1')

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=linuxdo&returnTo=%2Freports%2Fr-1']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(getMeMock).toHaveBeenCalledWith({ allowUnauthorized: true })
    })

    expect(applyCustomSessionMock).toHaveBeenCalledWith({
      access_token: '',
      provider: 'linuxdo',
      user: {
        id: 'user-123',
        email: 'linuxdo@example.com',
      },
    })
    expect(navigateMock).toHaveBeenCalledWith('/reports/r-1', { replace: true })
  })

  it('uses the Supabase callback flow without calling backend /auth/me', async () => {
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'supabase-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })
    window.history.replaceState({}, '', '/auth/callback?provider=supabase&returnTo=%2Fprofile')

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=supabase&returnTo=%2Fprofile']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(getSessionMock).toHaveBeenCalled()
    })
    expect(getMeMock).not.toHaveBeenCalled()
    expect(applyCustomSessionMock).not.toHaveBeenCalled()
    expect(navigateMock).toHaveBeenCalledWith('/profile', { replace: true })
  })

  it('shows an error instead of hanging when LinuxDo callback session hydration fails', async () => {
    getMeMock.mockRejectedValue(new Error('Failed to load current user: 401'))
    window.history.replaceState({}, '', '/auth/callback?provider=linuxdo&returnTo=%2Freports%2Fr-1')

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=linuxdo&returnTo=%2Freports%2Fr-1']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(getMeMock).toHaveBeenCalledWith({ allowUnauthorized: true })
    })

    expect(await screen.findByText('An unexpected error occurred')).toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalledWith('/reports/r-1', { replace: true })
  })

  it('preserves returnTo when callback errors send users back to login', () => {
    window.history.replaceState(
      {},
      '',
      '/auth/callback?provider=linuxdo&returnTo=%2Freports%2Fr-1%3Ftab%3Dsummary&error=linuxdo_auth&error_description=denied',
    )

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=linuxdo&returnTo=%2Freports%2Fr-1%3Ftab%3Dsummary&error=linuxdo_auth&error_description=denied']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Back to login' })).toHaveAttribute(
      'href',
      '/login?returnTo=%2Freports%2Fr-1%3Ftab%3Dsummary',
    )
  })

  it('uses the plain login route for callback retry when returnTo is the default root', () => {
    window.history.replaceState(
      {},
      '',
      '/auth/callback?provider=linuxdo&returnTo=%2F&error=linuxdo_auth&error_description=denied',
    )

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=linuxdo&returnTo=%2F&error=linuxdo_auth&error_description=denied']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Back to login' })).toHaveAttribute(
      'href',
      '/login',
    )
  })

  it('renders a password recovery form instead of auto-navigating during Supabase recovery', async () => {
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'recovery-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })
    window.history.replaceState(
      {},
      '',
      '/auth/callback?provider=supabase&returnTo=%2Freports%2Fr-1&type=recovery',
    )
    window.location.hash = ''

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=supabase&returnTo=%2Freports%2Fr-1&type=recovery']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    expect(await screen.findByLabelText('New password')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirm new password')).toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it('validates that a new password is provided during recovery', async () => {
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'recovery-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })
    window.history.replaceState({}, '', '/auth/callback?provider=supabase')
    window.location.hash = '#access_token=recovery-token&type=recovery'

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=supabase']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Update password' }))

    expect(await screen.findByText('Please enter a new password.')).toBeInTheDocument()
    expect(updateUserMock).not.toHaveBeenCalled()
  })

  it('validates minimum password length during recovery', async () => {
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'recovery-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })
    window.history.replaceState({}, '', '/auth/callback?provider=supabase')
    window.location.hash = '#access_token=recovery-token&type=recovery'

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=supabase']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    fireEvent.change(await screen.findByLabelText('New password'), {
      target: { value: '12345' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: '12345' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))

    expect(await screen.findByText('Password must be at least 6 characters.')).toBeInTheDocument()
    expect(updateUserMock).not.toHaveBeenCalled()
  })

  it('validates matching passwords during recovery', async () => {
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'recovery-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })
    window.history.replaceState({}, '', '/auth/callback?provider=supabase')
    window.location.hash = '#access_token=recovery-token&type=recovery'

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=supabase']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    fireEvent.change(await screen.findByLabelText('New password'), {
      target: { value: 'password123' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'password321' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))

    expect(await screen.findByText('Passwords do not match.')).toBeInTheDocument()
    expect(updateUserMock).not.toHaveBeenCalled()
  })

  it('updates the password and returns to login after Supabase recovery completes', async () => {
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'recovery-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })
    window.history.replaceState({}, '', '/auth/callback?provider=supabase&returnTo=%2Freports%2Fr-1')
    window.location.hash = '#access_token=recovery-token&type=recovery'

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=supabase&returnTo=%2Freports%2Fr-1']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    fireEvent.change(await screen.findByLabelText('New password'), {
      target: { value: 'password123' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))

    await waitFor(() => {
      expect(updateUserMock).toHaveBeenCalledWith({ password: 'password123' })
    })
    expect(supabaseSignOutMock).toHaveBeenCalledWith({ scope: 'local' })
    expect(navigateMock).toHaveBeenCalledWith('/login', { replace: true })
  })

  it('shows an inline error when password recovery update fails', async () => {
    updateUserMock.mockResolvedValueOnce({
      data: { user: null },
      error: { message: 'Could not update password' },
    })
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'recovery-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })
    window.history.replaceState({}, '', '/auth/callback?provider=supabase')
    window.location.hash = '#access_token=recovery-token&type=recovery'

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=supabase']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    fireEvent.change(await screen.findByLabelText('New password'), {
      target: { value: 'password123' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))

    expect(await screen.findByText('Could not update password')).toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalledWith('/login', { replace: true })
  })

  it('shows an inline error when recovery sign-out fails after updating the password', async () => {
    supabaseSignOutMock.mockResolvedValueOnce({ error: { message: 'Could not finish sign-out' } })
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'recovery-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })
    window.history.replaceState({}, '', '/auth/callback?provider=supabase&type=recovery')
    window.location.hash = ''

    render(
      <MemoryRouter initialEntries={['/auth/callback?provider=supabase&type=recovery']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    fireEvent.change(await screen.findByLabelText('New password'), {
      target: { value: 'password123' },
    })
    fireEvent.change(screen.getByLabelText('Confirm new password'), {
      target: { value: 'password123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Update password' }))

    await waitFor(() => {
      expect(updateUserMock).toHaveBeenCalledWith({ password: 'password123' })
    })
    expect(supabaseSignOutMock).toHaveBeenCalledWith({ scope: 'local' })
    expect(await screen.findByText('Could not finish sign-out')).toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalledWith('/login', { replace: true })
  })
})

describe('AuthProvider token refresh scheduling', () => {
  beforeEach(() => {
    getMyProfileMock.mockReset()
    getMeMock.mockReset()
    getSessionMock.mockReset()
    getSessionMock.mockResolvedValue({ data: { session: null } })
    getMeMock.mockResolvedValue({ id: 'user-123', email: 'linuxdo@example.com' })
    getMyProfileMock.mockResolvedValue({
      display_name: '',
      avatar_url: '',
      bio: '',
      created_at: '2026-03-01T00:00:00Z',
      role: 'user',
    })
    localStorage.clear()
  })

  it('tries backend /auth/me bootstrap on the login route and falls back to anonymous', async () => {
    window.history.replaceState({}, '', '/login')
    getMeMock.mockRejectedValueOnce(new Error('Unauthorized'))

    render(
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <AuthStateProbe />
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('anonymous')).toBeInTheDocument()
    })
    expect(getSessionMock).toHaveBeenCalled()
    expect(getMeMock).toHaveBeenCalledWith({ allowUnauthorized: true })
  })

  it('boots LinuxDo session from backend /auth/me when supabase session is absent on home', async () => {
    window.history.replaceState({}, '', '/')

    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <AuthStateProbe />
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('user-123')).toBeInTheDocument()
    })
    expect(getSessionMock).toHaveBeenCalled()
    expect(getMeMock).toHaveBeenCalledWith({ allowUnauthorized: true })
  })

  it('does not call backend /auth/me when a Supabase session is already present', async () => {
    window.history.replaceState({}, '', '/')
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'supabase-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <AuthStateProbe />
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('supabase-user')).toBeInTheDocument()
    })
    expect(getMeMock).not.toHaveBeenCalled()
  })

  it('does not stay stuck in loading when getSession throws', async () => {
    window.history.replaceState({}, '', '/profile')
    getSessionMock.mockRejectedValueOnce(new Error('session bootstrap failed'))
    getMeMock.mockRejectedValueOnce(new Error('Unauthorized'))

    render(
      <MemoryRouter initialEntries={['/profile']}>
        <AuthProvider>
          <AuthStateProbe />
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('anonymous')).toBeInTheDocument()
    })
    expect(getSessionMock).toHaveBeenCalled()
    expect(getMeMock).toHaveBeenCalledWith({ allowUnauthorized: true })
  })

  it('keeps the LinuxDo session when backend logout fails', async () => {
    window.history.replaceState({}, '', '/')
    logoutAuthSessionMock.mockRejectedValueOnce(new Error('logout failed'))

    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <AuthSignOutProbe />
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('user-123')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'sign-out' }))

    expect(await screen.findByText('logout failed')).toBeInTheDocument()
    expect(screen.getByText('user-123')).toBeInTheDocument()
  })

  it('signs out Supabase sessions even when backend logout is unavailable', async () => {
    window.history.replaceState({}, '', '/')
    logoutAuthSessionMock.mockRejectedValueOnce(new Error('logout failed'))
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'supabase-token',
          user: { id: 'supabase-user', email: 'supabase@example.com' },
        },
      },
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <AuthSignOutProbe />
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('supabase-user')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'sign-out' }))

    await waitFor(() => {
      expect(supabaseSignOutMock).toHaveBeenCalled()
    })
    expect(screen.getByText('anonymous')).toBeInTheDocument()
    expect(screen.queryByText('logout failed')).not.toBeInTheDocument()
  })

  it('clears the history cache when auth switches to a different signed-in user', async () => {
    window.history.replaceState({}, '', '/')
    getSessionMock.mockResolvedValueOnce({
      data: {
        session: {
          access_token: 'first-token',
          user: { id: 'user-123', email: 'first@example.com' },
        },
      },
    })

    render(
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>
          <AuthStateProbe />
        </AuthProvider>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('user-123')).toBeInTheDocument()
    })
    const callCountBeforeSwitch = clearHistoryCacheMock.mock.calls.length
    expect(authStateChangeCallback).toBeTypeOf('function')

    act(() => {
      authStateChangeCallback?.('SIGNED_IN', {
        access_token: 'second-token',
        user: { id: 'user-456', email: 'second@example.com' },
      })
    })

    await waitFor(() => {
      expect(screen.getByText('user-456')).toBeInTheDocument()
    })
    expect(clearHistoryCacheMock.mock.calls.length).toBe(callCountBeforeSwitch + 1)
  })
})
