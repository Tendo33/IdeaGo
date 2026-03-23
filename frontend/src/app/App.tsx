import { Button } from '@/components/ui/Button'
import { Component, Suspense, lazy, useEffect, useRef, useState, type ReactNode, type ErrorInfo } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useTranslation, withTranslation, type WithTranslation } from 'react-i18next'
import { Check, History, ArrowLeft, AlertTriangle, Monitor, Moon, Sun } from 'lucide-react'
import { Toaster } from 'sonner'
import { AuthProvider } from '@/lib/auth/AuthProvider'
import { ProtectedRoute, AdminRoute } from '@/lib/auth/ProtectedRoute'
import { useAuth } from '@/lib/auth/useAuth'
import { UserMenu } from '@/features/auth/components/UserMenu'

const HomePage = lazy(async () => {
  const page = await import('@/features/home/HomePage')
  return { default: page.HomePage }
})

const LandingPage = lazy(async () => {
  const page = await import('@/features/landing/LandingPage')
  return { default: page.LandingPage }
})

const LoginPage = lazy(async () => {
  const page = await import('@/features/auth/LoginPage')
  return { default: page.LoginPage }
})

const AuthCallback = lazy(async () => {
  const page = await import('@/features/auth/AuthCallback')
  return { default: page.AuthCallback }
})

const ProfilePage = lazy(async () => {
  const page = await import('@/features/profile/ProfilePage')
  return { default: page.ProfilePage }
})

const ReportPage = lazy(async () => {
  const page = await import('@/features/reports/ReportPage')
  return { default: page.ReportPage }
})

const HistoryPage = lazy(async () => {
  const page = await import('@/features/history/HistoryPage')
  return { default: page.HistoryPage }
})

const AdminPage = lazy(async () => {
  const page = await import('@/features/admin/AdminPage')
  return { default: page.AdminPage }
})

const TermsPage = lazy(async () => {
  const page = await import('@/features/legal/TermsPage')
  return { default: page.TermsPage }
})

const PrivacyPage = lazy(async () => {
  const page = await import('@/features/legal/PrivacyPage')
  return { default: page.PrivacyPage }
})

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

interface ErrorBoundaryProps extends WithTranslation {
  children: ReactNode
}

type ThemeMode = 'system' | 'light' | 'dark'

const THEME_MODE_STORAGE_KEY = 'ideago-theme-mode'
const THEME_MEDIA_QUERY = '(prefers-color-scheme: dark)'

function isThemeMode(value: string | null): value is ThemeMode {
  return value === 'system' || value === 'light' || value === 'dark'
}

function getSystemPrefersDark() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false
  }
  return window.matchMedia(THEME_MEDIA_QUERY).matches
}

function readStoredThemeMode(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'system'
  }
  const stored = window.localStorage.getItem(THEME_MODE_STORAGE_KEY)
  return isThemeMode(stored) ? stored : 'system'
}

function applyTheme(mode: ThemeMode, systemPrefersDark: boolean) {
  const root = document.documentElement
  const shouldUseDark = mode === 'dark' || (mode === 'system' && systemPrefersDark)
  root.classList.toggle('dark', shouldUseDark)
  root.style.colorScheme = shouldUseDark ? 'dark' : 'light'
}

function useThemeMode() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(() => readStoredThemeMode())
  const [systemPrefersDark, setSystemPrefersDark] = useState(() => getSystemPrefersDark())

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return

    const mediaQueryList = window.matchMedia(THEME_MEDIA_QUERY)
    const listener = (event: MediaQueryListEvent) => setSystemPrefersDark(event.matches)

    if (typeof mediaQueryList.addEventListener === 'function') {
      mediaQueryList.addEventListener('change', listener)
      return () => mediaQueryList.removeEventListener('change', listener)
    }

    mediaQueryList.addListener(listener)
    return () => mediaQueryList.removeListener(listener)
  }, [])

  useEffect(() => {
    window.localStorage.setItem(THEME_MODE_STORAGE_KEY, themeMode)
    applyTheme(themeMode, systemPrefersDark)
  }, [themeMode, systemPrefersDark])

  return {
    themeMode,
    selectThemeMode: (mode: ThemeMode) => setThemeMode(mode),
  }
}

const THEME_OPTIONS: Array<{
  mode: ThemeMode
  labelKey: string
  shortLabelKey: string
  Icon: typeof Monitor
}> = [
  { mode: 'system', labelKey: 'theme.system', shortLabelKey: 'theme.systemShort', Icon: Monitor },
  { mode: 'dark', labelKey: 'theme.dark', shortLabelKey: 'theme.darkShort', Icon: Moon },
  { mode: 'light', labelKey: 'theme.light', shortLabelKey: 'theme.lightShort', Icon: Sun },
]

function ThemeModeMenu({
  themeMode,
  onSelectThemeMode,
}: {
  themeMode: ThemeMode
  onSelectThemeMode: (mode: ThemeMode) => void
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const activeTheme = THEME_OPTIONS.find(option => option.mode === themeMode) ?? THEME_OPTIONS[0]
  const ActiveIcon = activeTheme.Icon

  useEffect(() => {
    if (!open) return

    const onPointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen(previous => !previous)}
        className="topbar-action focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        aria-label={t('theme.toggle')}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <ActiveIcon className="h-5 w-5" aria-hidden="true" />
        <span className="hidden sm:inline">{t(activeTheme.shortLabelKey)}</span>
      </button>
      {open && (
        <div
          role="menu"
          aria-label={t('theme.options')}
          className="absolute right-0 top-full mt-2 w-48 border-2 border-border bg-background p-2 shadow z-50"
        >
          {THEME_OPTIONS.map(option => {
            const OptionIcon = option.Icon
            const selected = option.mode === themeMode
            return (
              <button
                key={option.mode}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
                onClick={() => {
                  onSelectThemeMode(option.mode)
                  setOpen(false)
                }}
                className={`w-full inline-flex items-center justify-between px-3 py-2 text-sm font-bold uppercase tracking-wider transition-all cursor-pointer border-2 border-transparent ${
                  selected
                    ? 'bg-primary text-primary-foreground border-border shadow-sm'
                    : 'text-muted-foreground hover:bg-muted hover:border-border hover:shadow-sm hover:text-foreground'
                }`}
              >
                <span className="inline-flex items-center gap-3">
                  <OptionIcon className="h-4 w-4" aria-hidden="true" />
                  {t(option.labelKey)}
                </span>
                {selected && <Check className="h-4 w-4" aria-hidden="true" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

class ErrorBoundaryInner extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    const { t } = this.props
    if (this.state.hasError) {
      return (
        <div className="min-h-screen px-4 py-10 bg-background text-foreground flex items-center justify-center">
          <div className="max-w-xl w-full border-4 border-destructive bg-destructive/10 p-8 md:p-12 shadow-lg shadow-destructive text-center">
            <AlertTriangle className="w-16 h-16 text-destructive mx-auto mb-6" aria-hidden="true" />
            <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tighter mb-4 text-destructive break-words">
              {t('error.title')}
            </h1>
            <p className="text-lg font-bold text-destructive/80 mb-8 border-l-4 border-destructive pl-4 text-left break-words whitespace-pre-wrap">
              {this.state.error?.message ?? t('error.fallbackMessage')}
            </p>
            <Button
              variant="destructive"
              size="lg"
              onClick={() => {
                this.setState({ hasError: false, error: null })
                window.location.href = '/'
              }}
            >
              <ArrowLeft className="w-5 h-5 mr-3" aria-hidden="true" />
              {t('error.backToHome')}
            </Button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

const ErrorBoundary = withTranslation()(ErrorBoundaryInner)

function NotFound() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  return (
    <div className="app-shell px-4 min-h-[70vh] flex items-center justify-center">
      <div className="max-w-xl w-full border-4 border-border bg-card p-8 md:p-16 shadow-lg text-center">
        <h1 className="mb-4 text-8xl font-black text-muted-foreground/30 leading-none">404</h1>
          <h2 className="mb-6 text-3xl font-black uppercase tracking-tight text-foreground break-words">{t('error.notFoundTitle')}</h2>
        <p className="mb-10 text-lg font-bold text-muted-foreground break-words">{t('error.notFoundMessage')}</p>
        <Button
          size="lg"
          onClick={() => navigate('/')}
        >
          <ArrowLeft className="w-5 h-5 mr-3" aria-hidden="true" />
          {t('error.backToHome')}
        </Button>
      </div>
    </div>
  )
}

function NavBar({
  themeMode,
  onSelectThemeMode,
}: {
  themeMode: ThemeMode
  onSelectThemeMode: (mode: ThemeMode) => void
}) {
  const { t, i18n } = useTranslation()
  const currentLanguage = i18n.resolvedLanguage ?? i18n.language ?? 'en'
  const isChinese = currentLanguage.startsWith('zh')

  useEffect(() => {
    document.documentElement.lang = currentLanguage
  }, [currentLanguage])

  const toggleLanguage = () => {
    const newLang = isChinese ? 'en' : 'zh'
    i18n.changeLanguage(newLang)
  }

  return (
    <nav className="fixed left-0 right-0 top-0 z-50 border-b-4 border-border bg-background px-4 py-4 md:px-8 flex items-center justify-between shadow-sm no-print min-w-0">
      <Link
        to="/"
        className="inline-flex min-h-[44px] items-center px-2 sm:px-4 py-1.5 sm:py-2 border-2 border-border font-bold uppercase tracking-widest bg-primary text-primary-foreground shadow-sm cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none rounded-none hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-none transition-all truncate max-w-[50vw] sm:max-w-none text-xs sm:text-base"
      >
        {t('app.title')} {t('app.titleHighlight')}
      </Link>
      <div className="flex items-center gap-2 sm:gap-3 md:gap-4 shrink-0">
        <ThemeModeMenu themeMode={themeMode} onSelectThemeMode={onSelectThemeMode} />
        <button
          onClick={toggleLanguage}
          className="topbar-action min-w-[44px] px-2 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          aria-label={isChinese ? 'Switch to English' : '切换到中文'}
          aria-pressed={isChinese}
        >
          {isChinese ? 'EN' : 'ZH'}
        </button>
        <Link
          to="/reports"
          className="topbar-action bg-secondary text-secondary-foreground min-w-[44px] px-2 sm:px-4 focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
          aria-label={t('app.history')}
        >
          <History className="w-5 h-5 shrink-0" aria-hidden="true" />
          <span className="hidden sm:inline">{t('app.history')}</span>
        </Link>
        <UserMenu />
      </div>
    </nav>
  )
}

function RouteLoading() {
  const { t } = useTranslation()
  return (
    <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
      <div data-testid="route-loading" className="border-4 border-border bg-card px-12 py-8 text-center shadow-lg">
        <div className="w-8 h-8 bg-primary border-2 border-border mx-auto mb-4 animate-spin"></div>
        <p className="text-sm font-black uppercase tracking-widest text-muted-foreground">{t('loading.page')}</p>
      </div>
    </div>
  )
}

function HomeOrLanding() {
  const { user, loading } = useAuth()
  if (loading) return <RouteLoading />
  return user ? <HomePage /> : <LandingPage />
}

function AppShell({ themeMode, onSelectThemeMode }: { themeMode: ThemeMode; onSelectThemeMode: (m: ThemeMode) => void }) {
  const { t } = useTranslation()
  const { user, loading } = useAuth()
  const showNav = !loading && user !== null

  return (
    <>
      <a href="#main-content" className="skip-to-content">
        {t('app.skipToContent')}
      </a>
      {showNav && <NavBar themeMode={themeMode} onSelectThemeMode={onSelectThemeMode} />}
      <main
        id="main-content"
        className={`pb-16 min-h-screen bg-background text-foreground overflow-x-hidden ${showNav ? 'pt-24 sm:pt-32' : ''}`}
      >
        <Suspense fallback={<RouteLoading />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/auth/callback" element={<AuthCallback />} />
            <Route path="/" element={<HomeOrLanding />} />
            <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
            <Route path="/reports/:id" element={<ProtectedRoute><ReportPage /></ProtectedRoute>} />
            <Route path="/reports" element={<ProtectedRoute><HistoryPage /></ProtectedRoute>} />
            <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>
    </>
  )
}

export default function App() {
  const { themeMode, selectThemeMode } = useThemeMode()

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppShell themeMode={themeMode} onSelectThemeMode={selectThemeMode} />
          <Toaster
            position="bottom-right"
            toastOptions={{
              className: 'border-2 border-border bg-background text-foreground font-bold shadow-lg',
            }}
          />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
