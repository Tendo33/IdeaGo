import { useEffect, useState, type ReactNode } from 'react'
import { supabase } from '@/lib/supabase/client'
import {
  clearCustomAuthSession,
  readCustomAuthSession,
  setAccessToken,
} from '@/lib/auth/token'
import { AuthContext } from './AuthContext'
import type { AuthSession } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [initialCustomSession] = useState<AuthSession | null>(() => readCustomAuthSession())
  const [session, setSession] = useState<AuthSession | null>(initialCustomSession)
  const [loading, setLoading] = useState(initialCustomSession === null)

  useEffect(() => {
    if (initialCustomSession) {
      setAccessToken(initialCustomSession.access_token)
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
  }, [initialCustomSession])

  const signOut = async () => {
    clearCustomAuthSession()
    await supabase.auth.signOut()
    setSession(null)
    setAccessToken(null)
  }

  return (
    <AuthContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        loading,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
