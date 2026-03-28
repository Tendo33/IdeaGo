export interface ReturnToLocationLike {
  pathname?: string
  search?: string
  hash?: string
}

export const DEFAULT_AUTH_RETURN_TO = '/'

export function normalizeAuthReturnTo(value: string | null | undefined): string {
  const raw = (value ?? '').trim()
  if (!raw) return DEFAULT_AUTH_RETURN_TO

  if (raw.startsWith('/')) {
    return raw.startsWith('//') ? DEFAULT_AUTH_RETURN_TO : raw
  }

  try {
    const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
    const parsed = new URL(raw, origin)
    if (parsed.origin !== origin) {
      return DEFAULT_AUTH_RETURN_TO
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}` || DEFAULT_AUTH_RETURN_TO
  } catch {
    return DEFAULT_AUTH_RETURN_TO
  }
}

export function buildReturnToFromLocation(location: ReturnToLocationLike | null | undefined): string {
  if (!location?.pathname) return DEFAULT_AUTH_RETURN_TO
  return normalizeAuthReturnTo(`${location.pathname}${location.search ?? ''}${location.hash ?? ''}`)
}

export function readCurrentReturnTo(): string {
  if (typeof window === 'undefined') return DEFAULT_AUTH_RETURN_TO
  return normalizeAuthReturnTo(
    `${window.location.pathname}${window.location.search}${window.location.hash}`,
  )
}

export function buildLoginRedirectTarget(returnTo: string): string {
  const target = normalizeAuthReturnTo(returnTo)
  if (target === DEFAULT_AUTH_RETURN_TO) {
    return '/login'
  }
  return `/login?${new URLSearchParams({ returnTo: target }).toString()}`
}

export function buildAuthCallbackUrl(
  origin: string,
  provider: 'linuxdo' | 'supabase',
  returnTo: string,
): string {
  const params = new URLSearchParams({
    provider,
    returnTo: normalizeAuthReturnTo(returnTo),
  })
  return `${origin}/auth/callback?${params.toString()}`
}
