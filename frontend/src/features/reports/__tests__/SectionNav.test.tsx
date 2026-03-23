import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SectionNav } from '@/features/reports/components/SectionNav'

describe('SectionNav', () => {
  it('announces navigation label and active section state', () => {
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        observe() {}
        disconnect() {}
      },
    )

    Object.defineProperty(window, 'scrollY', {
      configurable: true,
      value: 400,
    })

    const overview = document.createElement('section')
    overview.id = 'section-summary'
    document.body.appendChild(overview)

    const competitors = document.createElement('section')
    competitors.id = 'section-competitors'
    document.body.appendChild(competitors)

    render(
      <SectionNav
        sections={[
          { id: 'section-summary', label: 'Overview' },
          { id: 'section-competitors', label: 'Competitors', count: 8 },
        ]}
      />,
    )

    fireEvent.scroll(window)

    expect(screen.getByRole('navigation', { name: 'Report sections' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Overview/i })).toHaveAttribute('aria-current', 'location')

    overview.remove()
    competitors.remove()
  })
})
