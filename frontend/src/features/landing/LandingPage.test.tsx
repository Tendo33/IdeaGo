import { render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { LandingPage } from './LandingPage'
import i18n from '@/lib/i18n/i18n'

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

  it('keeps key landing copy readable without forced truncation or line clamps', () => {
    render(
      <MemoryRouter>
        <LandingPage themeMode="system" onSelectThemeMode={vi.fn()} />
      </MemoryRouter>,
    )

    const mockQuery = screen.getByTitle(i18n.t('landing.mockQuery'))
    expect(mockQuery.className).not.toContain('line-clamp')

    const sourceLabel = screen.getByText('Product Hunt')
    expect(sourceLabel.className).not.toContain('truncate')

    const heroDescription = screen.getByText(i18n.t('landing.heroDesc'))
    expect(heroDescription.className).not.toContain('line-clamp')
  })

  it('removes repetitive feature and duplicate final cta sections', () => {
    render(
      <MemoryRouter>
        <LandingPage themeMode="system" onSelectThemeMode={vi.fn()} />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('heading', { name: i18n.t('landing.featuresTitle') })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: i18n.t('landing.ctaTitle') })).not.toBeInTheDocument()
  })
})
