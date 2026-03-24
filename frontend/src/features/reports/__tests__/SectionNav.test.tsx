import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SectionNav } from '@/features/reports/components/SectionNav'

describe('SectionNav', () => {
  const decisionFirstSections = [
    { id: 'section-should-we-build-this', label: 'Should we build this?' },
    { id: 'section-why-now', label: 'Why now' },
    { id: 'section-pain', label: 'Pain' },
    { id: 'section-whitespace', label: 'Whitespace' },
    { id: 'section-competitors', label: 'Competitors', count: 8 },
    { id: 'section-evidence-confidence', label: 'Evidence & confidence' },
  ]

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

    const sectionElements = decisionFirstSections.map(section => {
      const sectionElement = document.createElement('section')
      sectionElement.id = section.id
      document.body.appendChild(sectionElement)
      return sectionElement
    })

    render(
      <SectionNav sections={decisionFirstSections} />,
    )

    fireEvent.scroll(window)

    expect(screen.getByRole('navigation', { name: 'Report sections' })).toBeInTheDocument()
    const buttons = screen.getAllByRole('button')
    expect(buttons.map(button => button.textContent)).toEqual([
      'Should we build this?',
      'Why now',
      'Pain',
      'Whitespace',
      'Competitors(8)',
      'Evidence & confidence',
    ])
    expect(buttons[0]).toHaveAttribute('aria-current', 'location')

    sectionElements.forEach(section => section.remove())
  })
})
