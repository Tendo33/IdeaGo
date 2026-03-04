import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CompetitorCard } from '../CompetitorCard'
import type { Competitor } from '../../types/research'

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

  it('falls back to generic label for malformed links', () => {
    const invalidLinkCompetitor: Competitor = {
      ...competitorFixture,
      links: ['not-a-valid-url'],
    }
    render(<CompetitorCard competitor={invalidLinkCompetitor} rank={1} variant="standard" />)
    expect(screen.getByRole('link', { name: 'Open Example Product on link' })).toHaveTextContent('link')
  })
})
