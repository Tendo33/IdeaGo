import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { LoginPage } from './LoginPage'

const navigateMock = vi.fn()
const signUpMock = vi.fn()

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
  }),
}))

vi.mock('@/lib/supabase/client', () => ({
  supabase: {
    auth: {
      signInWithOAuth: vi.fn(),
      signInWithPassword: vi.fn(),
      signUp: (...args: unknown[]) => signUpMock(...args),
      resetPasswordForEmail: vi.fn(),
    },
  },
}))

describe('LoginPage registration locale metadata', () => {
  beforeEach(() => {
    authUser = null
    currentLanguage = 'zh-CN'
    navigateMock.mockReset()
    signUpMock.mockReset()
    signUpMock.mockResolvedValue({ error: null })
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
})
