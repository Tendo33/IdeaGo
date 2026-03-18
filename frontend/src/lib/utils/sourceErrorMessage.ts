import type { SourceStatus } from '../types/research'

const LEGACY_LLM_EXTRACTION_PREFIX = 'llm extraction failed:'
const EXTRACTION_UNAVAILABLE_MESSAGE = 'Extraction unavailable; showing raw results.'

export function normalizeSourceErrorMessage(
  status: SourceStatus,
  errorMessage: string | null,
): string | null {
  if (!errorMessage) {
    return null
  }
  if (errorMessage.toLowerCase().includes(LEGACY_LLM_EXTRACTION_PREFIX)) {
    return EXTRACTION_UNAVAILABLE_MESSAGE
  }
  if (status === 'degraded' && errorMessage.trim() === '') {
    return EXTRACTION_UNAVAILABLE_MESSAGE
  }
  return errorMessage
}
