import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ComparePanel } from '../ComparePanel'
import type { Competitor } from '../../types/research'

const competitors: Competitor[] = [
  {
    name: 'Comp A',
    links: ['https://a.example.com'],
    one_liner: 'A',
    features: ['f1'],
    pricing: null,
    strengths: ['s1'],
    weaknesses: ['w1'],
    relevance_score: 0.8,
    source_platforms: ['github'],
    source_urls: ['https://a.example.com'],
  },
  {
    name: 'Comp B',
    links: ['https://b.example.com'],
    one_liner: 'B',
    features: ['f2'],
    pricing: null,
    strengths: ['s2'],
    weaknesses: ['w2'],
    relevance_score: 0.7,
    source_platforms: ['tavily'],
    source_urls: ['https://b.example.com'],
  },
]

describe('ComparePanel', () => {
  it('renders with dialog semantics and supports Escape close', () => {
    const onClose = vi.fn()

    render(
      <ComparePanel
        competitors={competitors}
        onRemove={vi.fn()}
        onClose={onClose}
      />,
    )

    expect(screen.getByRole('dialog', { name: 'Comparing 2 Competitors' })).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})
