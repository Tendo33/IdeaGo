import { useCallback, useEffect, useState, type ReactNode } from 'react'
import type { Session as SupabaseSession } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase/client'
import { setAccessToken } from '@/lib/auth/token'
import { AuthContext } from './AuthContext'
import type { AuthSession } from './AuthContext'
import { getMe, getMyProfile, logoutAuthSession } from '@/lib/api/client'

const COOKIE_RECOVERY_ROUTE_PREFIXES = ['/profile', '/reports', '/admin'] as const

function toSupabaseSession(session: SupabaseSession): AuthSession {
  return {
    access_token: session.access_token,
    provider: 'supabase',
    user: {
      id: session.user.id,
      email: session.user.email ?? '',
    },
  }
}

function shouldRecoverCookieSession(pathname: string): boolean {
  return COOKIE_RECOVERY_ROUTE_PREFIXES.some(prefix => (
    pathname === prefix || pathname.startsWith(`${prefix}/`)
  ))
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [role, setRole] = useState<string>('user')

  const applySupabaseSession = useCallback((nextSession: SupabaseSession) => {
    setSession(toSupabaseSession(nextSession))
    setAccessToken(nextSession.access_token)
    setRole('user')
  }, [])

  const applyCustomSession = useCallback((nextSession: AuthSession) => {
    setSession(nextSession)
    setAccessToken(nextSession.access_token || null)
    setRole('user')
    setLoading(false)
  }, [])

  const signOut = useCallback(async () => {
    await Promise.allSettled([
      logoutAuthSession(),
      supabase.auth.signOut(),
    ])
    setSession(null)
    setAccessToken(null)
    setRole('user')
  }, [])

  const patchUser = useCallback((updates: Partial<AuthSession['user']>) => {
    setSession(previous => {
      if (!previous) return previous
      return {
        ...previous,
        user: {
          ...previous.user,
          ...updates,
        },
      }
    })
  }, [])

  useEffect(() => {
    let cancelled = false

    const bootstrap = async () => {
      try {
        const { data: { session: supabaseSession } } = await supabase.auth.getSession()
        if (cancelled) return

        if (supabaseSession?.access_token && supabaseSession.user?.id) {
          applySupabaseSession(supabaseSession)
          setLoading(false)
          return
        }
      } catch {
        // Ignore Supabase session bootstrap failure and fall back to cookie-backed /auth/me.
      }

      setAccessToken(null)
      if (!shouldRecoverCookieSession(window.location.pathname)) {
        setSession(null)
        setLoading(false)
        return
      }

      try {
        const me = await getMe({ allowUnauthorized: true })
        if (cancelled) return
        setSession({
          access_token: '',
          provider: 'linuxdo',
          user: { id: me.id, email: me.email ?? '' },
        })
      } catch {
        if (cancelled) return
        setSession(null)
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void bootstrap()

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      if (nextSession?.access_token && nextSession.user?.id) {
        applySupabaseSession(nextSession)
        return
      }

      setAccessToken(null)
      setSession(previous => (previous?.provider === 'linuxdo' ? previous : null))
    })

    return () => {
      cancelled = true
      subscription.unsubscribe()
    }
  }, [applySupabaseSession])

  const userId = session?.user?.id
  useEffect(() => {
    if (!userId) return
    let cancelled = false
    getMyProfile()
      .then(profile => {
        if (cancelled) return
        if (profile.display_name) {
          patchUser({ display_name: profile.display_name })
        }
        if (profile.role) {
          setRole(profile.role)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [patchUser, userId])

  const effectiveRole = userId ? role : 'user'

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        role: effectiveRole,
        loading,
        signOut,
        applyCustomSession,
        patchUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
