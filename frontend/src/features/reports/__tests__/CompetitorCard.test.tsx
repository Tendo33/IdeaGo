import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CompetitorCard } from '@/features/reports/components/CompetitorCard'
import type { Competitor } from '@/lib/types/research'

const competitorFixture: Competitor = {
  name: 'Example Product',
  links: ['https://www.example.com/pricing'],
  one_liner: 'Short description',
  features: ['feature-a'],
  pricing: '$10/mo',
  strengths: ['fast'],
  weaknesses: ['new market'],
  relevance_score: 0.82,
  source_platforms: ['github'],
  source_urls: ['https://www.example.com/pricing'],
}

describe('CompetitorCard', () => {
  it('renders readable hostname without external favicon image', () => {
    const { container } = render(
      <CompetitorCard competitor={competitorFixture} rank={1} variant="standard" />,
    )

    const link = screen.getByRole('link', { name: 'Open Example Product on example.com' })
    expect(link).toHaveTextContent('example.com')
    expect(container.querySelector('img')).toBeNull()
    expect(container.innerHTML).not.toContain('google.com/s2/favicons')
  })

  it('does not render a link for URLs the browser cannot safely open', () => {
    // Competitor links are LLM-extracted from untrusted pages. A malformed value
    // used to render as `<a href="not-a-valid-url">link</a>`, which resolves
    // relative to our own origin and drops the user into a dead route. Anything
    // that is not plain http(s) — including `javascript:` — is now omitted.
    const invalidLinkCompetitor: Competitor = {
      ...competitorFixture,
      links: ['not-a-valid-url'],
    }
    render(<CompetitorCard competitor={invalidLinkCompetitor} rank={1} variant="standard" />)
    expect(screen.queryByRole('link', { name: /Open Example Product on/ })).toBeNull()
  })

  it('does not render a link for javascript: URLs', () => {
    const hostileCompetitor: Competitor = {
      ...competitorFixture,
      links: ['javascript:alert(1)'],
    }
    render(<CompetitorCard competitor={hostileCompetitor} rank={1} variant="standard" />)
    expect(screen.queryByRole('link', { name: /Open Example Product on/ })).toBeNull()
  })

  it('shows a preview of strengths and weaknesses in standard cards before expansion', () => {
    render(
      <CompetitorCard competitor={competitorFixture} rank={2} variant="standard" />,
    )

    expect(screen.getByText('Strengths')).toBeInTheDocument()
    expect(screen.getByText('Weaknesses')).toBeInTheDocument()
    expect(screen.getByText('fast')).toBeInTheDocument()
    expect(screen.getByText('new market')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'View details' }))

    expect(screen.getByRole('button', { name: 'Show less' })).toBeInTheDocument()
  })

  it('keeps long company names readable without truncating and keeps external links touch-friendly', () => {
    const longNameCompetitor: Competitor = {
      ...competitorFixture,
      name: 'A very long competitor name with multilingual copy 产品名称非常长并且需要完整显示',
    }

    render(<CompetitorCard competitor={longNameCompetitor} rank={3} variant="standard" />)

    const heading = screen.getByRole('heading', { level: 3, name: longNameCompetitor.name })
    expect(heading.className).not.toContain('truncate')
    expect(heading.className).toContain('break-words')

    const sourceLink = screen.getByRole('link', {
      name: `Open ${longNameCompetitor.name} on example.com`,
    })
    expect(sourceLink.className).toContain('min-h-[44px]')
  })
})
