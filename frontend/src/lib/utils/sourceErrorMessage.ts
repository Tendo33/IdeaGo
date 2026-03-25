import i18n from '../i18n/i18n'
import type { SourceStatus } from '../types/research'

const LEGACY_LLM_EXTRACTION_PREFIX = 'llm extraction failed:'

export function normalizeSourceErrorMessage(
  status: SourceStatus,
  errorMessage: string | null,
): string | null {
  if (errorMessage === null) {
    return null
  }
  if (errorMessage.trim() === '' && status !== 'degraded') {
    return null
  }
  if (status === 'degraded' && errorMessage.trim() === '') {
    return i18n.t('report.error.extractionUnavailable')
  }
  if (errorMessage.toLowerCase().includes(LEGACY_LLM_EXTRACTION_PREFIX)) {
    return i18n.t('report.error.extractionUnavailable')
  }
  return errorMessage
}
