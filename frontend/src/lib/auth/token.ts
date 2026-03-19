/**
 * Module-level store for the current Supabase access token.
 *
 * Updated by AuthProvider whenever the session changes so that the API
 * client can read it synchronously.
 */

let _accessToken: string | null = null

export function setAccessToken(token: string | null): void {
  _accessToken = token
}

export function getAccessToken(): string | null {
  return _accessToken
}
