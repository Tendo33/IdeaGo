import { useEffect, useRef, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/lib/auth/useAuth'
import { getUserDisplayName, getUserInitial, truncateMiddle } from '@/lib/auth/AuthContext'
import { PRICING_ENABLED } from '@/lib/featureFlags'
import { LogIn, LogOut, UserCog, ShieldCheck, Crown } from 'lucide-react'

export function UserMenu() {
  const { t } = useTranslation()
  const { user, role, signOut } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuItemRefs = useRef<Array<HTMLElement | null>>([])

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

  const menuItemCount = 1 + (PRICING_ENABLED ? 1 : 0) + (role === 'admin' ? 1 : 0) + 1

  const onTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex(0)
      setOpen(true)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex(menuItemCount - 1)
      setOpen(true)
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      setActiveIndex(0)
      setOpen(true)
    }
  }

  const focusMenuItem = (index: number) => {
    const next = (index + menuItemCount) % menuItemCount
    setActiveIndex(next)
    menuItemRefs.current[next]?.focus()
  }

  const onMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusMenuItem(activeIndex + 1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusMenuItem(activeIndex - 1)
      return
    }
    if (event.key === 'Home') {
      event.preventDefault()
      focusMenuItem(0)
      return
    }
    if (event.key === 'End') {
      event.preventDefault()
      focusMenuItem(menuItemCount - 1)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
      return
    }
    if (event.key === 'Tab') {
      setOpen(false)
    }
  }

  useEffect(() => {
    if (!open) return
    requestAnimationFrame(() => {
      menuItemRefs.current[activeIndex]?.focus()
    })
  }, [activeIndex, open])

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

  const displayName = getUserDisplayName(user)
  const initial = getUserInitial(user)
  const truncatedEmail = truncateMiddle(user.email, 36)

  return (
    <div className="relative" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(prev => !prev)}
        onKeyDown={onTriggerKeyDown}
        className="topbar-action min-w-[44px] px-2 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        aria-label={t('nav.userMenu')}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <div className="w-7 h-7 bg-primary text-primary-foreground flex items-center justify-center font-black text-sm border-2 border-border">
          {initial}
        </div>
        <span className="hidden sm:inline max-w-[140px] truncate text-sm" title={user.email}>
          {displayName}
        </span>
      </button>

      {open && (
        <div
          role="menu"
          aria-label={t('nav.userOptions')}
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 top-full mt-2 w-56 border-2 border-border bg-background p-2 shadow z-50"
        >
          <div className="px-3 py-2 border-b-2 border-border mb-2">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              {t('auth.signedInAs')}
            </p>
            <p className="text-sm font-bold truncate" title={displayName}>{displayName}</p>
            <p className="text-xs text-muted-foreground truncate" title={user.email}>{truncatedEmail}</p>
          </div>

          <Link
            to="/profile"
            role="menuitem"
            ref={node => {
              menuItemRefs.current[0] = node
            }}
            tabIndex={activeIndex === 0 ? 0 : -1}
            onClick={() => setOpen(false)}
            className="w-full inline-flex items-center gap-3 px-3 py-2 text-sm font-bold uppercase tracking-wider text-foreground border-2 border-transparent transition-all cursor-pointer hover:bg-muted hover:border-border"
          >
            <UserCog className="w-4 h-4" />
            {t('profile.title')}
          </Link>

          {PRICING_ENABLED && (
            <Link
              to="/pricing"
              role="menuitem"
              ref={node => {
                menuItemRefs.current[1] = node
              }}
              tabIndex={activeIndex === 1 ? 0 : -1}
              onClick={() => setOpen(false)}
              className="w-full inline-flex items-center gap-3 px-3 py-2 text-sm font-bold uppercase tracking-wider text-primary border-2 border-transparent transition-all cursor-pointer hover:bg-primary/10 hover:border-primary"
            >
              <Crown className="w-4 h-4" />
              {t('pricing.upgrade')}
            </Link>
          )}

          {role === 'admin' && (
            <Link
              to="/admin"
              role="menuitem"
              ref={node => {
                menuItemRefs.current[PRICING_ENABLED ? 2 : 1] = node
              }}
              tabIndex={activeIndex === (PRICING_ENABLED ? 2 : 1) ? 0 : -1}
              onClick={() => setOpen(false)}
              className="w-full inline-flex items-center gap-3 px-3 py-2 text-sm font-bold uppercase tracking-wider text-foreground border-2 border-transparent transition-all cursor-pointer hover:bg-muted hover:border-border"
            >
              <ShieldCheck className="w-4 h-4" />
              {t('admin.menuLabel')}
            </Link>
          )}

          <button
            type="button"
            role="menuitem"
            ref={node => {
              menuItemRefs.current[menuItemCount - 1] = node
            }}
            tabIndex={activeIndex === menuItemCount - 1 ? 0 : -1}
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
