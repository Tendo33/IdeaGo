import { Component, Suspense, lazy, useEffect, useRef, useState, type ReactNode, type ErrorInfo } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useTranslation, withTranslation, type WithTranslation } from 'react-i18next'
import { Check, ChevronDown, History, ArrowLeft, AlertTriangle, Monitor, Moon, Sun } from 'lucide-react'
import { HomePage } from './pages/HomePage'

const ReportPage = lazy(async () => {
  const page = await import('./pages/ReportPage')
  return { default: page.ReportPage }
})

const HistoryPage = lazy(async () => {
  const page = await import('./pages/HistoryPage')
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
        <ActiveIcon className="h-4 w-4" />
        <span className="hidden sm:inline">{activeTheme.shortLabel}</span>
        <ChevronDown className={`hidden h-3.5 w-3.5 transition-transform duration-200 sm:block ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Theme mode options"
          className="absolute right-0 top-full mt-2 w-40 rounded-xl border border-border/80 bg-popover/95 p-1 backdrop-blur-2xl shadow-xl z-50"
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
                className={`w-full inline-flex items-center justify-between rounded-lg px-2.5 py-2 text-xs transition-colors cursor-pointer ${
                  selected
                    ? 'bg-cta/12 text-cta'
                    : 'text-text-muted hover:bg-muted/65 hover:text-text'
                }`}
              >
                <span className="inline-flex items-center gap-2">
                  <OptionIcon className="h-3.5 w-3.5" />
                  {option.label}
                </span>
                {selected && <Check className="h-3.5 w-3.5" />}
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
        <div className="min-h-screen px-4 py-10 bg-bg">
          <div className="surface-card mx-auto mt-16 max-w-md px-6 py-10 text-center">
            <AlertTriangle className="w-12 h-12 text-warning mx-auto mb-4" />
            <h1 className="text-2xl font-bold font-heading text-text mb-2">
              {t('error.title')}
            </h1>
            <p className="text-sm text-text-muted mb-6">
              {this.state.error?.message ?? t('error.fallbackMessage')}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null })
                window.location.href = '/'
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-cta text-primary-foreground hover:bg-cta-hover transition-colors duration-200 cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
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
    <div className="app-shell px-4">
      <div className="surface-card mx-auto mt-16 max-w-xl px-6 py-10 text-center">
        <h1 className="mb-4 text-6xl font-bold text-text-dim">{t('error.notFoundTitle')}</h1>
        <p className="mb-6 text-lg text-text-muted">{t('error.notFoundMessage')}</p>
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 rounded-xl bg-cta px-4 py-2 text-primary-foreground transition-colors duration-200 hover:bg-cta-hover cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
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
    <nav className="fixed left-1/2 top-4 z-50 flex w-[calc(100%-1.5rem)] max-w-6xl -translate-x-1/2 items-center justify-between rounded-2xl border border-border/80 bg-bg-card/85 px-4 py-3 shadow-xl backdrop-blur-md no-print sm:px-5">
      <Link
        to="/"
        className="group min-h-11 inline-flex items-center gap-1.5 text-lg font-bold tracking-tight text-text transition-colors duration-200 hover:text-foreground cursor-pointer"
      >
        <span className="text-text">{t('app.title')}</span>
        <span className="inline-flex items-center rounded-md border border-primary/30 bg-primary px-2 py-0.5 text-[0.82em] leading-none text-primary-foreground shadow-sm transition-transform duration-200 group-hover:-translate-y-px">
          {t('app.titleHighlight')}
        </span>
      </Link>
      <div className="flex items-center gap-2 sm:gap-3">
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
          className="topbar-action text-sm"
          aria-label={t('app.history')}
        >
          <History className="w-5 h-5 sm:w-4 sm:h-4" />
          <span className="hidden sm:inline">{t('app.history')}</span>
        </Link>
      </div>
    </nav>
  )
}

function RouteLoading() {
  const { t } = useTranslation()
  return (
    <div className="app-shell px-4">
      <div data-testid="route-loading" className="surface-card mt-10 px-4 py-12 text-center text-sm text-text-dim">
        {t('loading.page')}
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
        <main className="pb-10 pt-24">
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
