export function sanitizeExternalUrl(rawUrl: string): string | null {
  const normalized = rawUrl.trim()
  if (!normalized) return null

  try {
    const parsed = new URL(normalized)
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return normalized
    }
    return null
  } catch {
    return normalized
  }
}
