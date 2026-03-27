import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { supabase } from '@/lib/supabase/client'
import { getMe } from '@/lib/api/client'
import { ArrowLeft, AlertTriangle } from 'lucide-react'
import { buttonVariants } from '@/components/ui/Button'

export function AuthCallback() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const [timedOut, setTimedOut] = useState(false)

  useEffect(() => {
    if (searchParams.get('error')) return
    getMe({ allowUnauthorized: true })
      .then(() => navigate('/', { replace: true }))
      .catch(() => {})
  }, [navigate, searchParams])

  const urlError = useMemo(() => {
    const errorParam = searchParams.get('error')
    if (!errorParam) return null
    return searchParams.get('error_description') || errorParam
  }, [searchParams])

  useEffect(() => {
    if (urlError) return

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_IN') {
        navigate('/', { replace: true })
      }
    })

    const timer = setTimeout(() => setTimedOut(true), 10000)

    return () => {
      subscription.unsubscribe()
      clearTimeout(timer)
    }
  }, [navigate, urlError])

  const error = urlError ?? (timedOut ? t('auth.callbackTimeout') : null)

  if (error) {
    return (
      <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
        <div className="max-w-md w-full border-4 border-border bg-card p-8 md:p-12 shadow-lg text-center">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-black uppercase tracking-tight mb-3">
            {t('auth.callbackError')}
          </h2>
          <p className="text-sm text-muted-foreground font-bold mb-6">{error}</p>
          <Link to="/login" className={buttonVariants()}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('auth.backToLogin')}
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
      <div className="border-4 border-border bg-card px-12 py-8 text-center shadow-lg">
        <div className="w-8 h-8 bg-primary border-2 border-border mx-auto mb-4 animate-spin" />
        <p className="text-sm font-black uppercase tracking-widest text-muted-foreground">
          {t('auth.signingIn')}
        </p>
      </div>
    </div>
  )
}
