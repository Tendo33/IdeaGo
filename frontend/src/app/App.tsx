import { Component, Suspense, lazy, useEffect, useRef, useState, type ReactNode, type ErrorInfo } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useTranslation, withTranslation, type WithTranslation } from 'react-i18next'
import { Check, History, ArrowLeft, AlertTriangle, Monitor, Moon, Sun } from 'lucide-react'
import { HomePage } from '@/features/home/HomePage'

const ReportPage = lazy(async () => {
  const page = await import('@/features/reports/ReportPage')
  return { default: page.ReportPage }
})

const HistoryPage = lazy(async () => {
  const page = await import('@/features/history/HistoryPage')
  return { default: page.HistoryPage }
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
  label: string
  shortLabel: string
  Icon: typeof Monitor
}> = [
  { mode: 'system', label: 'System', shortLabel: 'SYS', Icon: Monitor },
  { mode: 'dark', label: 'Dark', shortLabel: 'DARK', Icon: Moon },
  { mode: 'light', label: 'Light', shortLabel: 'LIGHT', Icon: Sun },
]

function ThemeModeMenu({
  themeMode,
  onSelectThemeMode,
}: {
  themeMode: ThemeMode
  onSelectThemeMode: (mode: ThemeMode) => void
}) {
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
        className="topbar-action"
        aria-label="Toggle theme mode"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <ActiveIcon className="h-5 w-5" />
        <span className="hidden sm:inline">{activeTheme.shortLabel}</span>
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Theme mode options"
          className="absolute right-0 top-full mt-2 w-48 border-2 border-border bg-background p-2 shadow-[4px_4px_0px_0px_var(--border)] z-50"
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
                    ? 'bg-primary text-primary-foreground border-border shadow-[2px_2px_0px_0px_var(--border)]'
                    : 'text-muted-foreground hover:bg-muted hover:border-border hover:shadow-[2px_2px_0px_0px_var(--border)] hover:text-foreground'
                }`}
              >
                <span className="inline-flex items-center gap-3">
                  <OptionIcon className="h-4 w-4" />
                  {option.label}
                </span>
                {selected && <Check className="h-4 w-4" />}
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
          <div className="max-w-xl w-full border-4 border-destructive bg-destructive/10 p-8 md:p-12 shadow-[8px_8px_0px_0px_var(--destructive)] text-center">
            <AlertTriangle className="w-16 h-16 text-destructive mx-auto mb-6" />
            <h1 className="text-3xl md:text-5xl font-black uppercase tracking-tighter mb-4 text-destructive">
              {t('error.title')}
            </h1>
            <p className="text-lg font-bold text-destructive/80 mb-8 border-l-4 border-destructive pl-4 text-left">
              {this.state.error?.message ?? t('error.fallbackMessage')}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null })
                window.location.href = '/'
              }}
              className="inline-flex items-center gap-3 bg-destructive text-destructive-foreground px-6 py-3 font-black uppercase tracking-widest text-lg border-2 border-destructive shadow-[4px_4px_0px_0px_var(--destructive)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--destructive)] transition-all cursor-pointer"
            >
              <ArrowLeft className="w-5 h-5" />
              {t('error.backToHome')}
            </button>
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
      <div className="max-w-xl w-full border-4 border-border bg-card p-8 md:p-16 shadow-[8px_8px_0px_0px_var(--border)] text-center">
        <h1 className="mb-4 text-8xl font-black text-muted-foreground/30 leading-none">404</h1>
        <h2 className="mb-6 text-3xl font-black uppercase tracking-tight text-foreground">{t('error.notFoundTitle')}</h2>
        <p className="mb-10 text-lg font-bold text-muted-foreground">{t('error.notFoundMessage')}</p>
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-3 bg-primary text-primary-foreground px-6 py-3 font-black uppercase tracking-widest text-lg border-2 border-border shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] transition-all cursor-pointer"
        >
          <ArrowLeft className="w-5 h-5" />
          {t('error.backToHome')}
        </button>
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

  const toggleLanguage = () => {
    const newLang = isChinese ? 'en' : 'zh'
    i18n.changeLanguage(newLang)
  }

  return (
    <nav className="fixed left-0 right-0 top-0 z-50 border-b-4 border-border bg-background px-4 py-4 md:px-8 flex items-center justify-between shadow-sm no-print">
      <Link
        to="/"
        className="group inline-flex items-center gap-3 cursor-pointer"
      >
        <span className="text-2xl font-black uppercase tracking-tighter text-foreground">{t('app.title')}</span>
        <span className="inline-flex items-center border-2 border-border bg-primary px-2 py-0.5 text-xs font-black uppercase tracking-widest text-primary-foreground shadow-[2px_2px_0px_0px_var(--border)] transition-transform duration-150 group-hover:-translate-y-px">
          {t('app.titleHighlight')}
        </span>
      </Link>
      <div className="flex items-center gap-3 sm:gap-4">
        <ThemeModeMenu themeMode={themeMode} onSelectThemeMode={onSelectThemeMode} />
        <button
          onClick={toggleLanguage}
          className="topbar-action"
          aria-label="Toggle language"
        >
          {isChinese ? 'EN' : 'ZH'}
        </button>
        <Link
          to="/reports"
          className="topbar-action bg-secondary text-secondary-foreground"
          aria-label={t('app.history')}
        >
          <History className="w-5 h-5" />
          <span className="hidden sm:inline">{t('app.history')}</span>
        </Link>
      </div>
    </nav>
  )
}

function RouteLoading() {
  const { t } = useTranslation()
  return (
    <div className="app-shell px-4 min-h-[50vh] flex items-center justify-center">
      <div data-testid="route-loading" className="border-4 border-border bg-card px-12 py-8 text-center shadow-[8px_8px_0px_0px_var(--border)]">
        <div className="w-8 h-8 bg-primary border-2 border-border mx-auto mb-4 animate-spin"></div>
        <p className="text-sm font-black uppercase tracking-widest text-muted-foreground">{t('loading.page')}</p>
      </div>
    </div>
  )
}

export default function App() {
  const { themeMode, selectThemeMode } = useThemeMode()

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <NavBar themeMode={themeMode} onSelectThemeMode={selectThemeMode} />
        <main className="pb-16 pt-32 min-h-screen bg-background text-foreground">
          <Suspense fallback={<RouteLoading />}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/reports/:id" element={<ReportPage />} />
              <Route path="/reports" element={<HistoryPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </main>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
