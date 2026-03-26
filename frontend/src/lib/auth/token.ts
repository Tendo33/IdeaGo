/**
 * Module-level store for the current Supabase access token.
 *
 * Updated by AuthProvider whenever the session changes so that the API
 * client can read it synchronously.
 */

let _accessToken: string | null = null
export const CUSTOM_AUTH_STORAGE_KEY = 'ideago_custom_auth_session'

export interface CustomAuthSession {
  access_token: string
  provider: string
  user: {
    id: string
    email: string
    display_name?: string
  }
}

export function setAccessToken(token: string | null): void {
  _accessToken = token
}

export function getAccessToken(): string | null {
  return _accessToken
}

export function readCustomAuthSession(): CustomAuthSession | null {
  try {
    const raw = window.localStorage.getItem(CUSTOM_AUTH_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<CustomAuthSession>
    if (!parsed || typeof parsed !== 'object') return null
    if (typeof parsed.access_token !== 'string' || !parsed.access_token) return null
    if (typeof parsed.provider !== 'string' || !parsed.provider) return null
    if (!parsed.user || typeof parsed.user !== 'object') return null
    const userId = typeof parsed.user.id === 'string' ? parsed.user.id : ''
    const email = typeof parsed.user.email === 'string' ? parsed.user.email : ''
    const displayName = typeof parsed.user.display_name === 'string'
      ? parsed.user.display_name
      : undefined
    if (!userId) return null
    return {
      access_token: parsed.access_token,
      provider: parsed.provider,
      user: { id: userId, email, ...(displayName ? { display_name: displayName } : {}) },
    }
  } catch {
    return null
  }
}

export function saveCustomAuthSession(session: CustomAuthSession): void {
  window.localStorage.setItem(CUSTOM_AUTH_STORAGE_KEY, JSON.stringify(session))
}

export function clearCustomAuthSession(): void {
  window.localStorage.removeItem(CUSTOM_AUTH_STORAGE_KEY)
}
