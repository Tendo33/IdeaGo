import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MarketOverview } from '@/features/reports/components/MarketOverview'

describe('MarketOverview', () => {
  it('does not render the context lens side panel', () => {
    render(
      <MarketOverview summary="The market is shifting quickly.\n\nTeams are looking for lighter tools." />,
    )

    expect(screen.queryByText('Context lens')).not.toBeInTheDocument()
    expect(screen.getByText(/The market is shifting quickly\./)).toBeInTheDocument()
    expect(screen.getByText(/Teams are looking for lighter tools\./)).toBeInTheDocument()
  })
})
