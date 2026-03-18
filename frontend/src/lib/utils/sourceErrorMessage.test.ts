import { describe, expect, it } from 'vitest'
import { normalizeSourceErrorMessage } from './sourceErrorMessage'

describe('normalizeSourceErrorMessage', () => {
  it('replaces legacy llm extraction failure text', () => {
    const normalized = normalizeSourceErrorMessage(
      'degraded',
      'LLM extraction failed: Failed to extract competitors: timeout',
    )

    expect(normalized).toBe('Extraction unavailable; showing raw results.')
  })

  it('preserves non-legacy error text', () => {
    const normalized = normalizeSourceErrorMessage('failed', 'Timeout')

    expect(normalized).toBe('Timeout')
  })
})
