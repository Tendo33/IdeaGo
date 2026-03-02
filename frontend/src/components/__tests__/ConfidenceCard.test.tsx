import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ConfidenceCard } from '../ConfidenceCard'
import type { ConfidenceMetrics } from '../../types/research'

const baseConfidence: ConfidenceMetrics = {
  sample_size: 12,
  source_coverage: 3,
  source_success_rate: 0.86,
  freshness_hint: 'Generated moments ago',
  score: 86,
}

describe('ConfidenceCard', () => {
  it('shows high, medium, low confidence bands', () => {
    const { rerender } = render(<ConfidenceCard confidence={baseConfidence} />)
    expect(screen.getByText('High Confidence')).toBeInTheDocument()

    rerender(<ConfidenceCard confidence={{ ...baseConfidence, score: 60 }} />)
    expect(screen.getByText('Moderate Confidence')).toBeInTheDocument()

    rerender(<ConfidenceCard confidence={{ ...baseConfidence, score: 20 }} />)
    expect(screen.getByText('Low Confidence')).toBeInTheDocument()
  })

  it('shows fallback message when confidence payload is missing', () => {
    render(<ConfidenceCard confidence={undefined} />)
    expect(screen.getByText('Transparency data is temporarily unavailable.')).toBeInTheDocument()
  })
})
