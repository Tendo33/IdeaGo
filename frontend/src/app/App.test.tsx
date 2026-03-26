import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import App from './App'
import { UserMenu } from '@/features/auth/components/UserMenu'
import { ProfilePage } from '@/features/profile/ProfilePage'

const mockUser = { id: 'u1', email: 'test@test.com', display_name: '' }
let authState: { user: typeof mockUser | null; loading: boolean } = {
  user: mockUser,
  loading: false,
}
const getMyProfileMock = vi.fn()
const getQuotaInfoMock = vi.fn()

vi.mock('@/lib/auth/useAuth', () => ({
  useAuth: () => ({
    session: authState.user ? { user: authState.user, access_token: 'tok' } : null,
    user: authState.user,
    loading: authState.loading,
    role: 'user',
    signOut: vi.fn(),
    applyCustomSession: vi.fn(),
    patchUser: vi.fn(),
  }),
}))

vi.mock('@/lib/auth/AuthProvider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/lib/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  AdminRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/features/home/HomePage', () => ({
  HomePage: () => <div>HOME PAGE</div>,
}))

vi.mock('@/features/landing/LandingPage', () => ({
  LandingPage: () => <div>LANDING PAGE</div>,
}))

vi.mock('@/features/auth/LoginPage', () => ({
  LoginPage: () => <div>LOGIN PAGE</div>,
}))

vi.mock('@/features/pricing/PricingPage', () => ({
  PricingPage: () => <div>PRICING PAGE</div>,
}))

vi.mock('@/features/reports/ReportPage', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return {
    ReportPage: () => <div>REPORT PAGE</div>,
  }
})

vi.mock('@/features/history/HistoryPage', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return {
    HistoryPage: () => <div>HISTORY PAGE</div>,
  }
})

vi.mock('@/hooks/useDocumentTitle', () => ({
  useDocumentTitle: vi.fn(),
}))

vi.mock('@/lib/api/client', () => ({
  getMyProfile: (...args: unknown[]) => getMyProfileMock(...args),
  getQuotaInfo: (...args: unknown[]) => getQuotaInfoMock(...args),
  updateMyProfile: vi.fn(),
  deleteAccount: vi.fn(),
}))

vi.mock('sonner', () => ({
  Toaster: () => null,
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('App route loading', () => {
  beforeEach(() => {
    localStorage.clear()
    authState = { user: mockUser, loading: false }
    window.history.pushState({}, '', '/reports/r-1')
  })

  it('shows route fallback before lazy page resolves', async () => {
    render(<App />)

    expect(screen.getByTestId('route-loading')).toBeInTheDocument()
    expect(await screen.findByText('REPORT PAGE')).toBeInTheDocument()
  })
})

function mockMatchMedia(matches: boolean) {
  const listeners = new Set<(event: MediaQueryListEvent) => void>()
  const mediaQueryList = {
    matches,
    media: '(prefers-color-scheme: dark)',
    onchange: null,
    addEventListener: (_: 'change', listener: (event: MediaQueryListEvent) => void) => {
      listeners.add(listener)
    },
    removeEventListener: (_: 'change', listener: (event: MediaQueryListEvent) => void) => {
      listeners.delete(listener)
    },
    dispatchEvent: () => true,
  } as unknown as MediaQueryList

  vi.stubGlobal('matchMedia', vi.fn().mockImplementation(() => mediaQueryList))
}

describe('App landing page', () => {
  beforeEach(() => {
    localStorage.clear()
    window.history.pushState({}, '', '/')
  })

  it('shows landing page when not authenticated', async () => {
    authState = { user: null, loading: false }
    render(<App />)
    expect(await screen.findByText('LANDING PAGE')).toBeInTheDocument()
  })

  it('shows home page when authenticated', async () => {
    authState = { user: mockUser, loading: false }
    render(<App />)
    expect(await screen.findByText('HOME PAGE')).toBeInTheDocument()
  })

  it('hides pricing route behind not found', async () => {
    authState = { user: null, loading: false }
    window.history.pushState({}, '', '/pricing')
    render(<App />)

    expect(await screen.findByText('404')).toBeInTheDocument()
  })
})

describe('App signed-out navigation', () => {
  beforeEach(() => {
    localStorage.clear()
    authState = { user: null, loading: false }
    window.history.pushState({}, '', '/login')
  })

  it('does not show pricing entry on login', async () => {
    render(<App />)
    expect(await screen.findByText('LOGIN PAGE')).toBeInTheDocument()

    expect(screen.queryByRole('link', { name: /pricing|choose your plan/i })).not.toBeInTheDocument()
  })
})

describe('App user menu', () => {
  beforeEach(() => {
    localStorage.clear()
    authState = { user: mockUser, loading: false }
    window.history.pushState({}, '', '/')
  })

  it('does not show upgrade entry in the user menu', async () => {
    render(<App />)
    expect(await screen.findByText('HOME PAGE')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /user menu/i }))

    expect(screen.queryByRole('menuitem', { name: /upgrade to pro/i })).not.toBeInTheDocument()
  })
})

describe('Identity presentation', () => {
  beforeEach(() => {
    localStorage.clear()
    window.history.pushState({}, '', '/')
    authState = {
      user: {
        id: 'u-long',
        email: '4ca4ehmtfb5ldd803yab0w07bniuzev4bs8sga9tysa9r9web5@privaterelay.linux.do',
        display_name: 'LinuxDoCoder',
      },
      loading: false,
    }
    getMyProfileMock.mockReset()
    getQuotaInfoMock.mockReset()
    getMyProfileMock.mockResolvedValue({
      display_name: 'LinuxDoCoder',
      avatar_url: '',
      bio: '',
      created_at: '2026-03-01T00:00:00Z',
      role: 'user',
    })
    getQuotaInfoMock.mockResolvedValue({
      usage_count: 0,
      plan_limit: 5,
      plan: 'free',
      reset_at: '2026-03-27T08:00:00Z',
    })
  })

  it('prefers display name in the top navigation instead of a long relay email', async () => {
    const currentUser = authState.user!
    render(
      <MemoryRouter>
        <UserMenu />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: /user menu/i })).toHaveTextContent('LinuxDoCoder')
    expect(screen.getByTitle(currentUser.email)).toBeInTheDocument()
  })

  it('truncates the profile email field while preserving the full value in a tooltip', async () => {
    const currentUser = authState.user!
    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('LinuxDoCoder')).toBeInTheDocument()

    const emailInput = screen.getByLabelText('Email') as HTMLInputElement
    expect(emailInput.value).not.toBe(currentUser.email)
    expect(emailInput).toHaveAttribute('title', currentUser.email)
  })
})

describe('App theme mode', () => {
  beforeEach(() => {
    localStorage.clear()
    authState = { user: mockUser, loading: false }
    document.documentElement.classList.remove('dark')
    window.history.pushState({}, '', '/')
  })

  it('follows system preference in system mode', async () => {
    mockMatchMedia(true)
    render(<App />)
    expect(await screen.findByText('HOME PAGE')).toBeInTheDocument()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('selects theme mode from dropdown and persists choice', async () => {
    mockMatchMedia(true)
    render(<App />)
    expect(await screen.findByText('HOME PAGE')).toBeInTheDocument()

    const themeButton = screen.getByLabelText('Toggle theme mode')
    fireEvent.click(themeButton)
    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Light' }))

    expect(localStorage.getItem('ideago-theme-mode')).toBe('light')
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('restores manual theme from localStorage', async () => {
    localStorage.setItem('ideago-theme-mode', 'dark')
    mockMatchMedia(false)
    render(<App />)
    expect(await screen.findByText('HOME PAGE')).toBeInTheDocument()
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})

describe('App nav branding', () => {
  beforeEach(() => {
    localStorage.clear()
    authState = { user: mockUser, loading: false }
    window.history.pushState({}, '', '/')
  })

  it('renders logo highlight as high-contrast badge', async () => {
    mockMatchMedia(false)
    render(<App />)
    expect(await screen.findByText('HOME PAGE')).toBeInTheDocument()

    const logoLink = screen.getByRole('link', { name: /idea\s*go/i })
    expect(within(logoLink).getByText(/idea\s+go/i)).toBeInTheDocument()
    expect(logoLink).toHaveClass('bg-primary')
    expect(logoLink).toHaveClass('text-primary-foreground')
  })
})
