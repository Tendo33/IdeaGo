import {
  API_BASE,
  DEFAULT_TIMEOUT_MS,
  authHeaders,
  buildErrorMessage,
  fetchWithTimeout,
  mutationHeaders,
  type RequestOptions,
  throwApiError,
} from './core'

export interface QuotaInfo {
  usage_count: number
  plan_limit: number
  plan: string
  reset_at?: string
  error?: string
}

export interface UserProfile {
  display_name: string
  avatar_url: string
  bio: string
  created_at: string
  role?: string
}

export interface DeleteAccountResult {
  status: 'deleted'
  cleanup: {
    domain_data: string
    billing: string
    auth_identity: string
    profile: 'rolled_back' | 'restored_access_only' | 'deletion_pending' | 'rollback_failed' | 'deleted'
  }
}

export interface StartLinuxDoAuthOptions {
  redirectTo: string
  captchaToken: string
}

export interface CurrentUser {
  id: string
  email: string
}

export async function refreshAuthToken(options: RequestOptions = {}): Promise<string> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/refresh`,
    { method: 'POST', headers: mutationHeaders() },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Token refresh failed'))
  const data = await res.json()
  return data.access_token
}

export async function startLinuxDoAuth(
  { redirectTo, captchaToken }: StartLinuxDoAuthOptions,
  options: RequestOptions = {},
): Promise<string> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/linuxdo/start`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...mutationHeaders(),
      },
      body: JSON.stringify({
        redirect_to: redirectTo,
        captcha_token: captchaToken,
        prefetch: true,
      }),
    },
    { ...options, allowUnauthorized: true },
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'LinuxDo login failed'))
  const data = await res.json()
  const url = typeof data?.url === 'string' ? data.url.trim() : ''
  if (!url) {
    throw new Error('LinuxDo login failed: Missing authorize URL')
  }
  return url
}

export async function getMe(options: RequestOptions = {}): Promise<CurrentUser> {
  const res = await fetchWithTimeout(`${API_BASE}/auth/me`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load current user'))
  return res.json()
}

export async function logoutAuthSession(options: RequestOptions = {}): Promise<void> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/logout`,
    { method: 'POST', headers: mutationHeaders() },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to logout'))
}

export async function getQuotaInfo(options: RequestOptions = {}): Promise<QuotaInfo> {
  const res = await fetchWithTimeout(`${API_BASE}/auth/quota`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load quota'))
  return res.json()
}

export async function getMyProfile(options: RequestOptions = {}): Promise<UserProfile> {
  const res = await fetchWithTimeout(`${API_BASE}/auth/profile`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load profile'))
  return res.json()
}

export async function updateMyProfile(
  payload: Pick<UserProfile, 'display_name' | 'bio'>,
  options: RequestOptions = {},
): Promise<UserProfile> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/profile`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...mutationHeaders() },
      body: JSON.stringify(payload),
    },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to update profile'))
  return res.json()
}

export async function deleteAccount(options: RequestOptions = {}): Promise<DeleteAccountResult> {
  const res = await fetchWithTimeout(
    `${API_BASE}/auth/account`,
    { method: 'DELETE', headers: mutationHeaders() },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) await throwApiError(res, 'Failed to delete account')
  return res.json()
}
