import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ConfidenceCard } from '@/features/reports/components/ConfidenceCard'
import type { ConfidenceMetrics } from '@/lib/types/research'

const baseConfidence: ConfidenceMetrics = {
  sample_size: 12,
  source_coverage: 3,
  source_success_rate: 0.86,
  source_diversity: 3,
  evidence_density: 0.78,
  recency_score: 0.82,
  degradation_penalty: 0.1,
  contradiction_penalty: 0.05,
  reasons: ['Evidence spans multiple independent sources.'],
  freshness_hint: 'Generated moments ago',
  score: 86,
}

describe('ConfidenceCard', () => {
  it('shows high, medium, low confidence bands', () => {
    const { rerender } = render(<ConfidenceCard confidence={baseConfidence} />)
    expect(screen.getByText('High Reliability')).toBeInTheDocument()

    rerender(<ConfidenceCard confidence={{ ...baseConfidence, score: 60 }} />)
    expect(screen.getByText('Moderate Reliability')).toBeInTheDocument()

    rerender(<ConfidenceCard confidence={{ ...baseConfidence, score: 20 }} />)
    expect(screen.getByText('Low Reliability')).toBeInTheDocument()
  })

  it('renders richer trust factors, reasons, and penalties', () => {
    render(
      <ConfidenceCard
        confidence={{
          ...baseConfidence,
          source_diversity: 4,
          evidence_density: 0.64,
          recency_score: 0.71,
          degradation_penalty: 0.22,
          contradiction_penalty: 0.18,
          reasons: [
            'Evidence spans 4 distinct source platforms.',
            'Conflicting or uncertain evidence reduced confidence.',
          ],
        }}
      />,
    )

    expect(screen.getByText('Source diversity')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('Evidence density')).toBeInTheDocument()
    expect(screen.getByText('64%')).toBeInTheDocument()
    expect(screen.getByText('Degradation penalty')).toBeInTheDocument()
    expect(screen.getByText('22%')).toBeInTheDocument()
    expect(screen.getByText('Contradiction penalty')).toBeInTheDocument()
    expect(screen.getByText('18%')).toBeInTheDocument()
    expect(screen.getByText('Penalties Applied')).toBeInTheDocument()
    expect(screen.getByText('Evidence spans 4 distinct source platforms.')).toBeInTheDocument()
    expect(screen.getByText('Conflicting or uncertain evidence reduced confidence.')).toBeInTheDocument()
  })

  it('shows fallback message when confidence payload is missing', () => {
    render(<ConfidenceCard confidence={undefined} />)
    expect(screen.getAllByText('Data quality metrics are currently unavailable.').length).toBeGreaterThan(0)
    expect(screen.queryByText('No Major Penalties')).not.toBeInTheDocument()
    expect(screen.queryByText('0/100')).not.toBeInTheDocument()
  })
})
