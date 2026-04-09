import {
  API_BASE,
  DEFAULT_TIMEOUT_MS,
  authHeaders,
  buildErrorMessage,
  fetchWithTimeout,
  mutationHeaders,
  type RequestOptions,
} from './core'

export interface AdminUser {
  id: string
  display_name: string
  avatar_url: string
  bio: string
  created_at: string
  plan: string
  usage_count: number
  plan_limit: number
  role: string
  auth_provider: string
}

export interface AdminStats {
  total_users: number
  total_reports: number
  active_processing: number
  plan_breakdown: Record<string, number>
}

export async function adminListUsers(
  options: RequestOptions & { limit?: number; offset?: number } = {},
): Promise<AdminUser[]> {
  const { limit, offset, ...rest } = options
  const params = new URLSearchParams()
  if (typeof limit === 'number') params.set('limit', String(limit))
  if (typeof offset === 'number') params.set('offset', String(offset))
  const query = params.toString()
  const url = query ? `${API_BASE}/admin/users?${query}` : `${API_BASE}/admin/users`
  const res = await fetchWithTimeout(url, { headers: authHeaders() }, rest, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to list users'))
  return res.json()
}

export async function adminGetStats(options: RequestOptions = {}): Promise<AdminStats> {
  const res = await fetchWithTimeout(`${API_BASE}/admin/stats`, { headers: authHeaders() }, options, DEFAULT_TIMEOUT_MS)
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to load stats'))
  return res.json()
}

export async function adminSetQuota(
  userId: string,
  payload: { plan_limit?: number; usage_count?: number },
  options: RequestOptions = {},
): Promise<void> {
  const res = await fetchWithTimeout(
    `${API_BASE}/admin/users/${userId}/quota`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...mutationHeaders() },
      body: JSON.stringify(payload),
    },
    options,
    DEFAULT_TIMEOUT_MS,
  )
  if (!res.ok) throw new Error(await buildErrorMessage(res, 'Failed to update quota'))
}
