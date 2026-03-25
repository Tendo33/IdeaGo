import { describe, expect, it } from 'vitest'
import i18n from '../i18n/i18n'
import { normalizeSourceErrorMessage } from './sourceErrorMessage'

describe('normalizeSourceErrorMessage', () => {
  it('replaces legacy llm extraction failure text', () => {
    const normalized = normalizeSourceErrorMessage(
      'degraded',
      'LLM extraction failed: Failed to extract competitors: timeout',
    )

    expect(normalized).toBe('Structured extraction is unavailable. Showing raw results instead.')
  })

  it('uses the active app language for the extraction fallback message', async () => {
    await i18n.changeLanguage('zh')

    const normalized = normalizeSourceErrorMessage(
      'degraded',
      'LLM extraction failed: Failed to extract competitors: timeout',
    )

    expect(normalized).toBe('暂时无法提取结构化结果，现显示原始结果。')

    await i18n.changeLanguage('en')
  })

  it('uses the extraction fallback message for degraded sources with an empty string', () => {
    const normalized = normalizeSourceErrorMessage('degraded', '')

    expect(normalized).toBe('Structured extraction is unavailable. Showing raw results instead.')
  })

  it('preserves non-legacy error text', () => {
    const normalized = normalizeSourceErrorMessage('failed', 'Timeout')

    expect(normalized).toBe('Timeout')
  })

  it('treats empty non-degraded error text as absent', () => {
    const normalized = normalizeSourceErrorMessage('failed', '')

    expect(normalized).toBeNull()
  })
})
