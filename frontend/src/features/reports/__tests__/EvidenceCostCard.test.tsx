import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EvidenceCostCard } from '@/features/reports/components/EvidenceCostCard'
import type { EvidenceSummary } from '@/lib/types/research'

const evidenceSummary: EvidenceSummary = {
  top_evidence: ['Alpha delivers stronger integration coverage.'],
  evidence_items: [
    {
      title: 'Alpha Launch Notes',
      url: 'https://example.com/alpha',
      platform: 'github',
      snippet: 'Strong roadmap and broad feature support.',
    },
  ],
}

describe('EvidenceCostCard', () => {
  it('renders evidence list and source links', () => {
    render(<EvidenceCostCard evidenceSummary={evidenceSummary} />)

    expect(screen.getByText('Strong roadmap and broad feature support.')).toBeInTheDocument()

    const sourceLink = screen.getByRole('link', { name: /visit source/i })
    expect(sourceLink).toHaveAttribute('href', 'https://example.com/alpha')
  })

  it('renders empty state when no evidence items are available', () => {
    render(<EvidenceCostCard evidenceSummary={undefined} />)

    expect(screen.getByText('No specific evidence snippets are available for this report.')).toBeInTheDocument()
  })
})
