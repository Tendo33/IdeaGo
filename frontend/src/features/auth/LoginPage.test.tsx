import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { useContext } from 'react'
import { LoginPage } from './LoginPage'
import { AuthCallback } from './AuthCallback'
import { AuthContext } from '@/lib/auth/AuthContext'
import { AuthProvider } from '@/lib/auth/AuthProvider'

const navigateMock = vi.fn()
const signUpMock = vi.fn()
const signInWithPasswordMock = vi.fn()
const signInWithOAuthMock = vi.fn()
const applyCustomSessionMock = vi.fn()
const getMyProfileMock = vi.fn()
const getMeMock = vi.fn()
const getSessionMock = vi.fn()
const startLinuxDoAuthMock = vi.fn()
const turnstileRenderMock = vi.fn()
const turnstileResetMock = vi.fn()
const turnstileRemoveMock = vi.fn()

type TurnstileRenderOptions = {
  callback?: (token: string) => void
  'expired-callback'?: () => void
  'error-callback'?: () => void
  theme?: 'light' | 'dark' | 'auto'
}

let authUser: { id: string; email: string } | null = null
let currentLanguage = 'zh-CN'
let latestTurnstileOptions: TurnstileRenderOptions | null = null

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
      resetPasswordForEmail: vi.fn(),
      getSession: (...args: unknown[]) => getSessionMock(...args),
      onAuthStateChange: vi.fn(() => ({
        data: {
          subscription: {
            unsubscribe: vi.fn(),
          },
        },
      })),
    },
  },
}))

vi.mock('@/lib/api/client', () => ({
  getMyProfile: (...args: unknown[]) => getMyProfileMock(...args),
  getMe: (...args: unknown[]) => getMeMock(...args),
  startLinuxDoAuth: (...args: unknown[]) => startLinuxDoAuthMock(...args),
  logoutAuthSession: vi.fn(),
}))

function AuthStateProbe() {
  const auth = useContext(AuthContext)
  const user = auth?.user ?? null
  const loading = auth?.loading ?? true
  return <div>{loading ? 'loading' : (user?.id ?? 'anonymous')}</div>
}

describe('LoginPage registration locale metadata', () => {
  beforeEach(() => {
    authUser = null
    currentLanguage = 'zh-CN'
    latestTurnstileOptions = null
    navigateMock.mockReset()
    signUpMock.mockReset()
    signInWithPasswordMock.mockReset()
    signInWithOAuthMock.mockReset()
    applyCustomSessionMock.mockReset()
    getMyProfileMock.mockReset()
    getMeMock.mockReset()
    getSessionMock.mockReset()
    startLinuxDoAuthMock.mockReset()
    turnstileRenderMock.mockReset()
    turnstileResetMock.mockReset()
    turnstileRemoveMock.mockReset()
    vi.stubEnv('VITE_TURNSTILE_SITE_KEY', 'test-site-key')
    vi.stubEnv('VITE_API_BASE_URL', 'http://localhost:3000')
    installTurnstileMock()
    signUpMock.mockResolvedValue({ error: null })
    signInWithPasswordMock.mockResolvedValue({ error: null })
    signInWithOAuthMock.mockResolvedValue({ data: { provider: 'google', url: 'https://oauth.example.com' }, error: null })
    startLinuxDoAuthMock.mockResolvedValue('https://linux.do/oauth2/authorize?state=test')
    getSessionMock.mockResolvedValue({ data: { session: null } })
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
          data: {
            language: 'zh',
          },
        },
      })
    })
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

  it('passes captchaToken to password login and clears it after a successful submission', async () => {
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

    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
    expect(signInWithOAuthMock).not.toHaveBeenCalled()
    expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)
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

    fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
    expect(signInWithOAuthMock).not.toHaveBeenCalled()
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

    fireEvent.click(screen.getByRole('button', { name: 'Continue with GitHub' }))
    expect(signInWithOAuthMock).not.toHaveBeenCalled()
    expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)
  })

  it('blocks social sign-in until verified and prefetches LinuxDo redirect with captcha_token', async () => {
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
        <MemoryRouter initialEntries={['/login']}>
          <LoginPage />
        </MemoryRouter>,
      )

      fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
      expect(signInWithOAuthMock).not.toHaveBeenCalled()
      expect(screen.getAllByText('Verifying you are human...').length).toBeGreaterThan(0)

      act(() => {
        latestTurnstileOptions?.callback?.('turnstile-token')
      })

      fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
      await waitFor(() => {
        expect(signInWithOAuthMock).toHaveBeenCalledWith({
          provider: 'google',
          options: { redirectTo: 'https://ideago.simonsun.cc/auth/callback' },
        })
      })

      act(() => {
        latestTurnstileOptions?.callback?.('linuxdo-token')
      })
      fireEvent.click(screen.getByRole('button', { name: 'Continue with LinuxDo' }))

      await waitFor(() => {
        expect(startLinuxDoAuthMock).toHaveBeenCalledWith({
          redirectTo: 'https://ideago.simonsun.cc/auth/callback',
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

  it('verifies LinuxDo callback session via backend and redirects immediately', async () => {
    getMeMock.mockResolvedValue({ id: 'user-123', email: 'linuxdo@example.com' })
    window.history.replaceState({}, '', '/auth/callback')

    render(
      <MemoryRouter initialEntries={['/auth/callback']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(getMeMock).toHaveBeenCalledWith({ allowUnauthorized: true })
    })

    expect(navigateMock).toHaveBeenCalledWith('/', { replace: true })
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

  it('skips backend /auth/me bootstrap on signed-out public routes', async () => {
    window.history.replaceState({}, '', '/login')

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
    expect(getMeMock).not.toHaveBeenCalled()
  })

  it('boots LinuxDo session from backend /auth/me when supabase session is absent', async () => {
    window.history.replaceState({}, '', '/profile')

    render(
      <MemoryRouter initialEntries={['/profile']}>
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
})
