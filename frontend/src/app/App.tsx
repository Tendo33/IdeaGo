import { Button } from '@/components/ui/Button'
import { Toaster } from 'sonner'
import { Component, Suspense, lazy, useEffect, useState, type ErrorInfo, type ReactNode } from 'react'
import { BrowserRouter, Link, Route, Routes, useNavigate } from 'react-router-dom'
import { useTranslation, withTranslation, type WithTranslation } from 'react-i18next'
import { AlertTriangle, ArrowLeft, History } from 'lucide-react'
import { HomePage } from '@/features/home/HomePage'
import { ThemeModeMenu, type ThemeMode } from './ThemeModeMenu'

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

function resolveDocumentLanguage(language: string | undefined): string {
  if (!language) return 'en'
  const [normalized] = language.split('-')
  return normalized || 'en'
}

function getLanguageDisplayName(language: string, uiLanguage: string): string {
  const normalizedLanguage = resolveDocumentLanguage(language)
  const normalizedUiLanguage = resolveDocumentLanguage(uiLanguage)

  try {
    const displayNames = new Intl.DisplayNames([normalizedUiLanguage], { type: 'language' })
    return displayNames.of(normalizedLanguage) ?? normalizedLanguage.toUpperCase()
  } catch {
    return normalizedLanguage.toUpperCase()
  }
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
        <Button size="lg" onClick={() => navigate('/')}>
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
  const nextLanguage = isChinese ? 'en' : 'zh'
  const languageToggleLabel = getLanguageDisplayName(nextLanguage, currentLanguage)

  useEffect(() => {
    document.documentElement.lang = resolveDocumentLanguage(currentLanguage)
  }, [currentLanguage])

  const toggleLanguage = () => {
    i18n.changeLanguage(nextLanguage)
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
          aria-label={t('app.switchToLanguage', { language: languageToggleLabel })}
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

export default function App() {
  const { themeMode, selectThemeMode } = useThemeMode()

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <a href="#main-content" className="skip-to-content">
          Skip to content
        </a>
        <NavBar themeMode={themeMode} onSelectThemeMode={selectThemeMode} />
        <main id="main-content" className="pb-16 pt-24 sm:pt-32 min-h-screen bg-background text-foreground overflow-x-hidden">
          <Suspense fallback={<RouteLoading />}>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/reports/:id" element={<ReportPage />} />
              <Route path="/reports" element={<HistoryPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </main>
        <Toaster
          position="bottom-right"
          toastOptions={{
            className: 'border-2 border-border bg-background text-foreground font-bold shadow-lg',
          }}
        />
      </BrowserRouter>
    </ErrorBoundary>
  )
}
