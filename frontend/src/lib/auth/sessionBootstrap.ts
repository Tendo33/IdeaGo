import type { Session as SupabaseSession } from '@supabase/supabase-js'
import type { AuthSession } from './AuthContext'
import { getMe, getMyProfile } from '@/lib/api/client'

export function toSupabaseSession(session: SupabaseSession): AuthSession {
  return {
    access_token: session.access_token,
    provider: 'supabase',
    user: {
      id: session.user.id,
      email: session.user.email ?? '',
    },
  }
}

export function shouldRecoverCookieSession(pathname: string): boolean {
  return pathname !== '/auth/callback'
}

export async function bootstrapSupabaseSession(
  getSession: () => Promise<{ data: { session: SupabaseSession | null } }>,
): Promise<SupabaseSession | null> {
  const {
    data: { session },
  } = await getSession()
  if (session?.access_token && session.user?.id) {
    return session
  }
  return null
}

export async function recoverCookieSession(): Promise<AuthSession | null> {
  const me = await getMe({ allowUnauthorized: true })
  return {
    access_token: '',
    provider: 'linuxdo',
    user: { id: me.id, email: me.email ?? '' },
  }
}

export async function hydrateProfileRole(): Promise<{
  displayName: string
  role: string
}> {
  const profile = await getMyProfile()
  return {
    displayName: profile.display_name ?? '',
    role: profile.role ?? '',
  }
}
