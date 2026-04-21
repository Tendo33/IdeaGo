import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import type { Session as SupabaseSession } from '@supabase/supabase-js'
import { supabase } from '@/lib/supabase/client'
import { setAccessToken } from '@/lib/auth/token'
import { AuthContext, type AuthSession } from './AuthContext'
import { logoutAuthSession } from '@/lib/api/client'
import { clearHistoryCache } from '@/features/history/historyCache'
import {
  bootstrapSupabaseSession,
  hydrateProfileRole,
  recoverCookieSession,
  shouldRecoverCookieSession,
  toSupabaseSession,
} from './sessionBootstrap'

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
    setSession((previous: AuthSession | null) => {
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
        const supabaseSession = await bootstrapSupabaseSession(
          () => supabase.auth.getSession(),
        )
        if (cancelled) return

        if (supabaseSession) {
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
        const recoveredSession = await recoverCookieSession()
        if (cancelled) return
        setSession(recoveredSession)
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
      setSession((previous: AuthSession | null) => (previous?.provider === 'linuxdo' ? previous : null))
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
    hydrateProfileRole()
      .then(({ displayName, role: nextRole }) => {
        if (cancelled) return
        if (displayName) {
          patchUser({ display_name: displayName })
        }
        if (nextRole) {
          setRole(nextRole)
        }
        setRoleError(null)
        setRoleLoading(false)
      })
      .catch(error => {
        if (cancelled) return
        console.warn('Failed to hydrate auth profile', error)
        setRole((previous: string) => previous)
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
