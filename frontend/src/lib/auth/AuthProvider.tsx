import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { supabase } from '@/lib/supabase/client'
import {
  clearCustomAuthSession,
  readCustomAuthSession,
  saveCustomAuthSession,
  setAccessToken,
} from '@/lib/auth/token'
import { AuthContext } from './AuthContext'
import type { AuthSession } from './AuthContext'
import { getMyProfile, refreshAuthToken } from '@/lib/api/client'

function decodeJwtExp(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return typeof payload.exp === 'number' ? payload.exp : null
  } catch {
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [initialCustomSession] = useState<AuthSession | null>(() => readCustomAuthSession())
  const [session, setSession] = useState<AuthSession | null>(initialCustomSession)
  const [loading, setLoading] = useState(initialCustomSession === null)
  const [role, setRole] = useState<string>('user')
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const signOutRef = useRef<(() => Promise<void>) | undefined>(undefined)

  const signOut = useCallback(async () => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
    clearCustomAuthSession()
    await supabase.auth.signOut()
    setSession(null)
    setAccessToken(null)
    setRole('user')
  }, [])

  useEffect(() => {
    signOutRef.current = signOut
  }, [signOut])

  const scheduleTokenRefresh = useCallback((token: string) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)

    const exp = decodeJwtExp(token)
    if (!exp) return

    function doRefresh() {
      refreshAuthToken().then(newToken => {
        setAccessToken(newToken)
        const stored = readCustomAuthSession()
        if (stored) {
          saveCustomAuthSession({ ...stored, access_token: newToken })
          setSession(prev => prev ? { ...prev, access_token: newToken } : prev)
        }
        const nextExp = decodeJwtExp(newToken)
        if (nextExp) {
          const delay = nextExp * 1000 - Date.now() - 5 * 60 * 1000
          if (delay > 0) {
            refreshTimerRef.current = setTimeout(doRefresh, delay)
          }
        }
      }).catch(() => signOutRef.current?.())
    }

    const refreshAt = exp * 1000 - Date.now() - 5 * 60 * 1000
    if (refreshAt <= 0) {
      doRefresh()
      return
    }
    refreshTimerRef.current = setTimeout(doRefresh, refreshAt)
  }, [])

  const applyCustomSession = useCallback((nextSession: AuthSession) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
    saveCustomAuthSession(nextSession)
    setSession(nextSession)
    setAccessToken(nextSession.access_token)
    setRole('user')
    setLoading(false)
    scheduleTokenRefresh(nextSession.access_token)
  }, [scheduleTokenRefresh])

  const patchUser = useCallback((updates: Partial<AuthSession['user']>) => {
    setSession(prev => {
      if (!prev) return prev
      const nextSession = {
        ...prev,
        user: {
          ...prev.user,
          ...updates,
        },
      }
      if (prev.provider !== 'supabase') {
        saveCustomAuthSession(nextSession)
      }
      return nextSession
    })
  }, [])

  useEffect(() => {
    if (initialCustomSession) {
      setAccessToken(initialCustomSession.access_token)
      scheduleTokenRefresh(initialCustomSession.access_token)
      return
    }

    supabase.auth.getSession().then(({ data: { session: s } }) => {
      if (s?.access_token && s.user?.id) {
        setSession({
          access_token: s.access_token,
          provider: 'supabase',
          user: { id: s.user.id, email: s.user.email ?? '' },
        })
        setAccessToken(s.access_token)
      } else {
        setSession(null)
        setAccessToken(null)
      }
      setLoading(false)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, s) => {
      if (readCustomAuthSession()) return
      if (s?.access_token && s.user?.id) {
        setSession({
          access_token: s.access_token,
          provider: 'supabase',
          user: { id: s.user.id, email: s.user.email ?? '' },
        })
        setAccessToken(s.access_token)
      } else {
        setSession(null)
        setAccessToken(null)
      }
    })

    return () => subscription.unsubscribe()
  }, [initialCustomSession, scheduleTokenRefresh])

  const userId = session?.user?.id
  useEffect(() => {
    if (!userId) return
    let cancelled = false
    getMyProfile().then(profile => {
      if (!cancelled) {
        if (profile.display_name) {
          patchUser({ display_name: profile.display_name })
        }
        if (profile.role) {
          setRole(profile.role)
        }
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [patchUser, userId])

  const effectiveRole = userId ? role : 'user'

  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current)
    }
  }, [])

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
