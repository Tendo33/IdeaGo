import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { useContext } from 'react'
import { LoginPage } from './LoginPage'
import { AuthCallback } from './AuthCallback'
import { AuthContext } from '@/lib/auth/AuthContext'
import { AuthProvider } from '@/lib/auth/AuthProvider'

const navigateMock = vi.fn()
const signUpMock = vi.fn()
const applyCustomSessionMock = vi.fn()
const getMyProfileMock = vi.fn()
const refreshAuthTokenMock = vi.fn()

let authUser: { id: string; email: string } | null = null
let currentLanguage = 'zh-CN'

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
  readCustomAuthSession: vi.fn(() => {
    const raw = window.localStorage.getItem('ideago_custom_auth_session')
    return raw ? JSON.parse(raw) : null
  }),
  clearCustomAuthSession: vi.fn(),
}))

vi.mock('@/lib/supabase/client', () => ({
  supabase: {
  auth: {
      signInWithOAuth: vi.fn(),
      signInWithPassword: vi.fn(),
      signUp: (...args: unknown[]) => signUpMock(...args),
      resetPasswordForEmail: vi.fn(),
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
  refreshAuthToken: (...args: unknown[]) => refreshAuthTokenMock(...args),
}))

function encodeJwt(payload: Record<string, unknown>) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.signature`
}

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
    navigateMock.mockReset()
    signUpMock.mockReset()
    applyCustomSessionMock.mockReset()
    getMyProfileMock.mockReset()
    refreshAuthTokenMock.mockReset()
    signUpMock.mockResolvedValue({ error: null })
    window.history.replaceState({}, '', '/login')
    window.location.hash = ''
    localStorage.clear()
  })

  it('passes the current UI language to Supabase signUp metadata', async () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <LoginPage />
      </MemoryRouter>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sign Up' }))
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
          data: {
            language: 'zh',
          },
        },
      })
    })
  })

  it('applies LinuxDo callback session immediately without requiring a manual refresh', async () => {
    window.history.replaceState(
      {},
      '',
      '/auth/callback#access_token=test-token&provider=linuxdo&user_id=user-123&email=linuxdo@example.com',
    )

    render(
      <MemoryRouter initialEntries={['/auth/callback']}>
        <AuthCallback />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(applyCustomSessionMock).toHaveBeenCalledWith({
        access_token: 'test-token',
        provider: 'linuxdo',
        user: {
          id: 'user-123',
          email: 'linuxdo@example.com',
        },
      })
    })

    expect(navigateMock).toHaveBeenCalledWith('/', { replace: true })
  })
})

describe('AuthProvider token refresh scheduling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    refreshAuthTokenMock.mockReset()
    getMyProfileMock.mockReset()
    getMyProfileMock.mockResolvedValue({
      display_name: '',
      avatar_url: '',
      bio: '',
      created_at: '2026-03-01T00:00:00Z',
      role: 'user',
    })
    localStorage.clear()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('does not immediately refresh long-lived LinuxDo sessions', async () => {
    const nowMs = Date.UTC(2026, 2, 26, 12, 0, 0)
    vi.setSystemTime(nowMs)

    const accessToken = encodeJwt({
      sub: 'user-123',
      email: 'linuxdo@example.com',
      provider: 'linuxdo',
      exp: Math.floor((nowMs + 30 * 24 * 60 * 60 * 1000) / 1000),
    })

    localStorage.setItem('ideago_custom_auth_session', JSON.stringify({
      access_token: accessToken,
      provider: 'linuxdo',
      user: {
        id: 'user-123',
        email: 'linuxdo@example.com',
      },
    }))

    render(
      <AuthProvider>
        <AuthStateProbe />
      </AuthProvider>,
    )

    expect(screen.getByText('user-123')).toBeInTheDocument()
    await vi.advanceTimersByTimeAsync(1000)

    expect(refreshAuthTokenMock).not.toHaveBeenCalled()
  })
})
