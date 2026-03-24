import { Navigate, useLocation, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ShieldOff, ArrowLeft } from 'lucide-react'
import { useAuth } from './useAuth'
import { buttonVariants } from '@/components/ui/Button'

function RouteLoadingSpinner() {
  const { t } = useTranslation()
  return (
    <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
      <div className="border-4 border-border bg-card px-12 py-8 text-center shadow-lg">
        <div className="w-8 h-8 bg-primary border-2 border-border mx-auto mb-4 animate-spin" />
        <p className="text-sm font-black uppercase tracking-widest text-muted-foreground">
          {t('loading.page')}
        </p>
      </div>
    </div>
  )
}

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <RouteLoadingSpinner />
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  return <>{children}</>
}

export function AdminRoute({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation()
  const { user, role, loading } = useAuth()
  const location = useLocation()

  if (loading) return <RouteLoadingSpinner />
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />

  if (role !== 'admin') {
    return (
      <div className="app-shell px-4 min-h-[70vh] flex items-center justify-center">
        <div className="max-w-xl w-full border-4 border-destructive bg-destructive/10 p-8 md:p-16 shadow-lg text-center">
          <ShieldOff className="w-16 h-16 text-destructive mx-auto mb-6" aria-hidden="true" />
          <h1 className="text-3xl font-black uppercase tracking-tight mb-4 text-destructive">
            {t('admin.forbidden')}
          </h1>
          <p className="text-lg font-bold text-destructive/80 mb-8">
            {t('admin.forbiddenMessage')}
          </p>
          <Link to="/" className={buttonVariants({ variant: 'destructive', size: 'lg' })}>
            <ArrowLeft className="w-5 h-5 mr-3" aria-hidden="true" />
            {t('error.backToHome')}
          </Link>
        </div>
      </div>
    )
  }

  return <>{children}</>
}
