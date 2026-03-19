import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const mockUser = { id: 'u1', email: 'test@test.com' }
let authState: { user: typeof mockUser | null; loading: boolean } = {
  user: mockUser,
  loading: false,
}

vi.mock('@/lib/auth/useAuth', () => ({
  useAuth: () => ({
    session: authState.user ? { user: authState.user, access_token: 'tok' } : null,
    user: authState.user,
    loading: authState.loading,
    signOut: vi.fn(),
  }),
}))

vi.mock('@/lib/auth/AuthProvider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/lib/auth/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('@/features/home/HomePage', () => ({
  HomePage: () => <div>HOME PAGE</div>,
}))

vi.mock('@/features/landing/LandingPage', () => ({
  LandingPage: () => <div>LANDING PAGE</div>,
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
