import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

vi.mock('./pages/HomePage', () => ({
  HomePage: () => <div>HOME PAGE</div>,
}))

vi.mock('./pages/ReportPage', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return {
    ReportPage: () => <div>REPORT PAGE</div>,
  }
})

vi.mock('./pages/HistoryPage', async () => {
  await new Promise(resolve => setTimeout(resolve, 30))
  return {
    HistoryPage: () => <div>HISTORY PAGE</div>,
  }
})

describe('App route loading', () => {
  beforeEach(() => {
    localStorage.clear()
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

describe('App theme mode', () => {
  beforeEach(() => {
    localStorage.clear()
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
    window.history.pushState({}, '', '/')
  })

  it('renders logo highlight as high-contrast badge', async () => {
    mockMatchMedia(false)
    render(<App />)
    expect(await screen.findByText('HOME PAGE')).toBeInTheDocument()

    const logoLink = screen.getByRole('link', { name: 'IdeaGo' })
    const logoHighlight = within(logoLink).getByText('Go')
    expect(logoHighlight).toHaveClass('bg-primary')
    expect(logoHighlight).toHaveClass('text-primary-foreground')
  })
})
