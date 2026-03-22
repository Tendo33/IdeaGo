import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
        <div className="border-4 border-border bg-card px-12 py-8 text-center shadow-lg">
          <div className="w-8 h-8 bg-primary border-2 border-border mx-auto mb-4 animate-spin" />
          <p className="text-sm font-black uppercase tracking-widest text-muted-foreground">
            Loading...
          </p>
        </div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
