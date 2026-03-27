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
  // Custom OAuth sessions are now cookie-backed and no longer persisted in browser storage.
  return null
}

export function saveCustomAuthSession(session: CustomAuthSession): void {
  void session
}

export function clearCustomAuthSession(): void {
  // Keep API compatibility for old call sites; no local storage state to clear.
}
