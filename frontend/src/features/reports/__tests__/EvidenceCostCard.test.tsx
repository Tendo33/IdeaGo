import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EvidenceCostCard } from '@/features/reports/components/EvidenceCostCard'
import type { EvidenceSummary } from '@/lib/types/research'

const evidenceSummary: EvidenceSummary = {
  top_evidence: [
    'Alpha delivers stronger integration coverage.',
    'Users repeatedly complain that setup takes too long.',
  ],
  evidence_items: [
    {
      title: 'Alpha Launch Notes',
      url: 'https://example.com/alpha',
      platform: 'github',
      snippet: 'Strong roadmap and broad feature support.',
      category: 'market',
      freshness_hint: '2026-03-20T10:00:00Z',
      matched_query: 'alpha integration coverage',
      query_family: 'competitor_discovery',
    },
    {
      title: 'Pain Thread',
      url: 'https://example.com/pain',
      platform: 'reddit',
      snippet: 'Setup still takes too long for first-time users.',
      category: 'pain',
      freshness_hint: '2026-03-18T08:00:00Z',
      matched_query: 'setup pain points',
      query_family: 'pain_discovery',
    },
    {
      title: 'Commercial Signal',
      url: 'https://example.com/commercial',
      platform: 'tavily',
      snippet: 'Teams compare budget for faster onboarding.',
      category: 'commercial',
      freshness_hint: '2026-03-15T08:00:00Z',
      matched_query: 'onboarding budget',
      query_family: 'commercial_discovery',
    },
    {
      title: 'Whitespace Wedge',
      url: 'https://example.com/whitespace',
      platform: 'github',
      snippet: 'Lightweight onboarding remains underserved.',
      category: 'whitespace',
      freshness_hint: '2026-03-14T08:00:00Z',
      matched_query: 'lightweight onboarding wedge',
      query_family: 'whitespace_discovery',
    },
    {
      title: 'Evidence Five',
      url: 'https://example.com/five',
      platform: 'github',
      snippet: 'Additional evidence item five.',
      category: 'market',
      freshness_hint: '2026-03-13T08:00:00Z',
      matched_query: 'evidence five',
      query_family: 'competitor_discovery',
    },
    {
      title: 'Evidence Six',
      url: 'https://example.com/six',
      platform: 'reddit',
      snippet: 'Additional evidence item six.',
      category: 'pain',
      freshness_hint: '2026-03-12T08:00:00Z',
      matched_query: 'evidence six',
      query_family: 'pain_discovery',
    },
    {
      title: 'Evidence Seven',
      url: 'https://example.com/seven',
      platform: 'tavily',
      snippet: 'Additional evidence item seven.',
      category: 'commercial',
      freshness_hint: '2026-03-11T08:00:00Z',
      matched_query: 'evidence seven',
      query_family: 'commercial_discovery',
    },
  ],
  category_counts: {
    market: 1,
    pain: 1,
    commercial: 1,
  },
  source_platforms: ['github', 'reddit'],
  freshness_distribution: {
    recent: 2,
    aging: 1,
  },
  degraded_sources: ['reddit'],
  uncertainty_notes: ['Evidence conflicts outside the early-adopter segment.'],
}

describe('EvidenceCostCard', () => {
  it('renders inspectable evidence and trust metadata', () => {
    render(<EvidenceCostCard evidenceSummary={evidenceSummary} />)

    expect(screen.getByText('Evidence highlights')).toBeInTheDocument()
    expect(screen.getByText('Users repeatedly complain that setup takes too long.')).toBeInTheDocument()
    expect(screen.getByText('Trust metadata')).toBeInTheDocument()
    expect(screen.getByText('market: 1')).toBeInTheDocument()
    expect(screen.getByText('recent: 2')).toBeInTheDocument()
    expect(screen.getByText('platform: github')).toBeInTheDocument()
    expect(screen.getByText('Trust warnings')).toBeInTheDocument()
    expect(screen.getByText('Degraded sources: reddit')).toBeInTheDocument()
    expect(screen.getByText('Evidence conflicts outside the early-adopter segment.')).toBeInTheDocument()
    expect(screen.getByText('family: competitor_discovery')).toBeInTheDocument()
    expect(screen.getByText('query: alpha integration coverage')).toBeInTheDocument()

    const sourceLinks = screen.getAllByRole('link', { name: /visit source/i })
    expect(sourceLinks[0]).toHaveAttribute('href', 'https://example.com/alpha')
  })

  it('expands to show additional inspectable evidence entries', async () => {
    render(<EvidenceCostCard evidenceSummary={evidenceSummary} />)

    expect(screen.queryByText('Whitespace Wedge')).not.toBeInTheDocument()
    expect(screen.queryByText('Evidence Seven')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /read full summary/i }))

    expect(screen.getByText('Whitespace Wedge')).toBeInTheDocument()
    expect(screen.getByText('Evidence Seven')).toBeInTheDocument()
  })

  it('renders empty state when no evidence items are available', () => {
    render(<EvidenceCostCard evidenceSummary={undefined} />)

    expect(
      screen.getByText('No specific evidence snippets are available for this report.'),
    ).toBeInTheDocument()
  })
})
