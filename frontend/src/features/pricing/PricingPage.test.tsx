import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { PricingPage } from './PricingPage'

vi.mock('@/lib/auth/useAuth', () => ({
  useAuth: () => ({ user: null }),
}))

describe('PricingPage visual normalization', () => {
  it('avoids blur/glassy hero decorations', () => {
    const { container } = render(
      <MemoryRouter>
        <PricingPage />
      </MemoryRouter>,
    )

    const blurred = container.querySelector('[class*="blur"]')
    expect(blurred).toBeNull()
  })
})
