import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { LoginPage } from './LoginPage'
import { AuthCallback } from './AuthCallback'

const navigateMock = vi.fn()
const signUpMock = vi.fn()
const applyCustomSessionMock = vi.fn()

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

describe('LoginPage registration locale metadata', () => {
  beforeEach(() => {
    authUser = null
    currentLanguage = 'zh-CN'
    navigateMock.mockReset()
    signUpMock.mockReset()
    applyCustomSessionMock.mockReset()
    signUpMock.mockResolvedValue({ error: null })
    window.history.replaceState({}, '', '/login')
    window.location.hash = ''
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
