import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Session as SupabaseSession } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase/client'
import { setAccessToken } from '@/lib/auth/token'
import { AuthContext } from './AuthContext'
import type { AuthSession } from './AuthContext'
import { getMe, getMyProfile, logoutAuthSession } from '@/lib/api/client'
import { clearHistoryCache } from '@/features/history/historyCache'

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
  return pathname !== '/auth/callback'
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [role, setRole] = useState<string>('')
  const [roleLoading, setRoleLoading] = useState(false)
  const [roleError, setRoleError] = useState<string | null>(null)
  const previousUserIdRef = useRef<string>('')

  const applySupabaseSession = useCallback((nextSession: SupabaseSession) => {
    setSession(toSupabaseSession(nextSession))
    setAccessToken(nextSession.access_token)
    setRole('')
    setRoleLoading(true)
    setRoleError(null)
  }, [])

  const applyCustomSession = useCallback((nextSession: AuthSession) => {
    setSession(nextSession)
    setAccessToken(nextSession.access_token || null)
    setRole('')
    setRoleLoading(true)
    setRoleError(null)
    setLoading(false)
  }, [])

  const signOut = useCallback(async () => {
    if (!session) return

    if (session.provider === 'supabase') {
      const result = await supabase.auth.signOut()
      if (result.error) {
        throw result.error
      }
    } else {
      await logoutAuthSession()
      await supabase.auth.signOut().catch(() => {})
    }

    setSession(null)
    setAccessToken(null)
    setRole('')
    setRoleLoading(false)
    setRoleError(null)
    clearHistoryCache()
  }, [session])

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
        setRole('')
        setRoleLoading(false)
        setRoleError(null)
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
        setRoleLoading(true)
        setRoleError(null)
      } catch {
        if (cancelled) return
        setSession(null)
        setRole('')
        setRoleLoading(false)
        setRoleError(null)
        clearHistoryCache()
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
      setRoleLoading(false)
    })

    return () => {
      cancelled = true
      subscription.unsubscribe()
    }
  }, [applySupabaseSession])

  const userId = session?.user?.id
  useEffect(() => {
    const previousUserId = previousUserIdRef.current
    if (!userId || (previousUserId && previousUserId !== userId)) {
      clearHistoryCache()
    }
    previousUserIdRef.current = userId ?? ''
  }, [userId])

  useEffect(() => {
    if (!userId) {
      setRole('')
      setRoleLoading(false)
      setRoleError(null)
      return
    }

    let cancelled = false
    setRoleLoading(true)
    getMyProfile()
      .then(profile => {
        if (cancelled) return
        if (profile.display_name) {
          patchUser({ display_name: profile.display_name })
        }
        if (profile.role) {
          setRole(profile.role)
        }
        setRoleError(null)
        setRoleLoading(false)
      })
      .catch(error => {
        if (cancelled) return
        console.warn('Failed to hydrate auth profile', error)
        setRole(previous => previous)
        setRoleError(error instanceof Error ? error.message : 'Failed to hydrate auth profile')
        setRoleLoading(false)
      })
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
        roleLoading,
        roleError,
        signOut,
        applyCustomSession,
        patchUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
