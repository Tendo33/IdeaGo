import { render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { LandingPage } from './LandingPage'

class MockIntersectionObserver implements IntersectionObserver {
  readonly root = null
  readonly rootMargin = ''
  readonly thresholds = []
  disconnect(): void {}
  observe(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return []
  }
  unobserve(): void {}
}

describe('LandingPage', () => {
  beforeAll(() => {
    vi.stubGlobal('IntersectionObserver', MockIntersectionObserver)
  })

  it('does not show a pricing entry in the public top navigation', () => {
    render(
      <MemoryRouter>
        <LandingPage themeMode="system" onSelectThemeMode={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('link', { name: /pricing|choose your plan/i })).not.toBeInTheDocument()
  })

  it('shows the theme mode toggle in the public top navigation', () => {
    render(
      <MemoryRouter>
        <LandingPage themeMode="system" onSelectThemeMode={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('button', { name: /theme|主题/i })).toBeInTheDocument()
  })
})
