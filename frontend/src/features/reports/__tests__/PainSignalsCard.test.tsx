import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PainSignalsCard } from '@/features/reports/components/PainSignalsCard'
import type { PainSignal } from '@/lib/types/research'

const signals: PainSignal[] = [
  {
    theme: 'Monitoring costs are too high',
    summary: 'Small teams keep asking for cheaper alternatives.',
    intensity: 0.85,
    frequency: 0.7,
    evidence_urls: [
      'https://example.com/evidence/monitoring-costs',
      'https://example.com/evidence/cheaper-alternatives',
    ],
    source_platforms: ['hackernews'],
  },
]

describe('PainSignalsCard', () => {
  it('lets users expand and click evidence links', () => {
    render(<PainSignalsCard signals={signals} />)

    fireEvent.click(screen.getByRole('button', { name: '2 evidence links' }))

    const evidenceLinks = screen.getAllByRole('link')
    expect(evidenceLinks).toHaveLength(2)
    expect(evidenceLinks[0]).toHaveAttribute(
      'href',
      'https://example.com/evidence/monitoring-costs',
    )
    expect(evidenceLinks[1]).toHaveAttribute(
      'href',
      'https://example.com/evidence/cheaper-alternatives',
    )
  })
})
