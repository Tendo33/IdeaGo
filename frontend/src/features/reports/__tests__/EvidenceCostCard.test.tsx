import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EvidenceCostCard } from '@/features/reports/components/EvidenceCostCard'
import type { CostBreakdown, EvidenceSummary, ReportMeta } from '@/lib/types/research'

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

const costBreakdown: CostBreakdown = {
  llm_calls: 4,
  llm_retries: 1,
  endpoint_failovers: 1,
  source_calls: 3,
  pipeline_latency_ms: 6200,
  tokens_prompt: 0,
  tokens_completion: 0,
}

const reportMeta: ReportMeta = {
  llm_fault_tolerance: {
    fallback_used: true,
    endpoints_tried: ['primary', 'backup-us'],
    last_error_class: 'retryable_http',
  },
}

describe('EvidenceCostCard', () => {
  it('renders evidence list and source links', () => {
    render(
      <EvidenceCostCard
        evidenceSummary={evidenceSummary}
        costBreakdown={costBreakdown}
        reportMeta={reportMeta}
      />,
    )

    expect(screen.getByText('Strong roadmap and broad feature support.')).toBeInTheDocument()

    const sourceLink = screen.getByRole('link', { name: /source/i })
    expect(sourceLink).toHaveAttribute('href', 'https://example.com/alpha')
  })

  it('renders cost metrics and fallback warning for missing payload', () => {
    const { rerender } = render(
      <EvidenceCostCard
        evidenceSummary={evidenceSummary}
        costBreakdown={costBreakdown}
        reportMeta={reportMeta}
      />,
    )
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('6s')).toBeInTheDocument()

    rerender(
      <EvidenceCostCard
        evidenceSummary={undefined}
        costBreakdown={undefined}
        reportMeta={undefined}
      />,
    )
    expect(screen.getByText('Transparency data is temporarily unavailable.')).toBeInTheDocument()
  })
})
