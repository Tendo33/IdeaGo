import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MarketOverview } from '@/features/reports/components/MarketOverview'

describe('MarketOverview', () => {
  it('keeps the context lens panel stacked with consistent spacing', () => {
    render(
      <MarketOverview summary="The market is shifting quickly.\n\nTeams are looking for lighter tools." />,
    )

    const contextLensHeading = screen.getByText('Context lens')
    const sidePanel = contextLensHeading.parentElement

    expect(sidePanel).not.toBeNull()
    expect(sidePanel).toHaveClass('gap-4')
  })
})
