import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/lib/auth/useAuth'
import { LogIn, LogOut, UserCog } from 'lucide-react'

export function UserMenu() {
  const { t } = useTranslation()
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  if (!user) {
    return (
      <Link
        to="/login"
        className="topbar-action bg-primary text-primary-foreground min-w-[44px] px-2 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        aria-label={t('auth.signIn')}
      >
        <LogIn className="w-5 h-5 shrink-0" />
        <span className="hidden sm:inline">{t('auth.signIn')}</span>
      </Link>
    )
  }

  const initial = (user.email?.charAt(0) ?? 'U').toUpperCase()

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen(prev => !prev)}
        className="topbar-action min-w-[44px] px-2 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        aria-label={t('nav.userMenu')}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <div className="w-7 h-7 bg-primary text-primary-foreground flex items-center justify-center font-black text-sm border-2 border-border">
          {initial}
        </div>
        <span className="hidden sm:inline max-w-[120px] truncate text-sm">
          {user.email}
        </span>
      </button>

      {open && (
        <div
          role="menu"
          aria-label={t('nav.userOptions')}
          className="absolute right-0 top-full mt-2 w-56 border-2 border-border bg-background p-2 shadow-[4px_4px_0px_0px_var(--border)] z-50"
        >
          <div className="px-3 py-2 border-b-2 border-border mb-2">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              {t('auth.signedInAs')}
            </p>
            <p className="text-sm font-bold truncate">{user.email}</p>
          </div>

          <Link
            to="/profile"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="w-full inline-flex items-center gap-3 px-3 py-2 text-sm font-bold uppercase tracking-wider text-foreground border-2 border-transparent transition-all cursor-pointer hover:bg-muted hover:border-border"
          >
            <UserCog className="w-4 h-4" />
            {t('profile.title')}
          </Link>

          <button
            type="button"
            role="menuitem"
            onClick={async () => {
              setOpen(false)
              await signOut()
              navigate('/')
            }}
            className="w-full inline-flex items-center gap-3 px-3 py-2 text-sm font-bold uppercase tracking-wider text-destructive border-2 border-transparent transition-all cursor-pointer hover:bg-destructive/10 hover:border-destructive"
          >
            <LogOut className="w-4 h-4" />
            {t('auth.signOut')}
          </button>
        </div>
      )}
    </div>
  )
}
