import { Component, Suspense, lazy, type ReactNode, type ErrorInfo } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import { useTranslation, withTranslation, type WithTranslation } from 'react-i18next'
import { History, ArrowLeft, AlertTriangle } from 'lucide-react'
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
        <div className="min-h-screen flex items-center justify-center px-4 bg-bg">
          <div className="max-w-md text-center">
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
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cta text-white hover:bg-cta-hover transition-colors duration-200 cursor-pointer"
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
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <h1 className="text-6xl font-bold font-heading text-text-dim mb-4">{t('error.notFoundTitle')}</h1>
      <p className="text-lg text-text-muted mb-6">{t('error.notFoundMessage')}</p>
      <button
        onClick={() => navigate('/')}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cta text-white hover:bg-cta-hover transition-colors duration-200 cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4" />
        {t('error.backToHome')}
      </button>
    </div>
  )
}

function NavBar() {
  const { t, i18n } = useTranslation()
  
  const toggleLanguage = () => {
    const newLang = i18n.language.startsWith('zh') ? 'en' : 'zh'
    i18n.changeLanguage(newLang)
  }

  return (
    <nav className="fixed top-4 left-4 right-4 z-50 flex items-center justify-between px-4 sm:px-5 py-3 rounded-xl bg-bg-card/80 backdrop-blur-md border border-border no-print">
      <Link
        to="/"
        className="text-lg font-bold font-heading text-text cursor-pointer hover:text-cta transition-colors duration-200 min-h-11 flex items-center"
      >
        {t('app.title')}<span className="text-cta">{t('app.titleHighlight')}</span>
      </Link>
      <div className="flex items-center gap-4">
        <button
          onClick={toggleLanguage}
          className="text-xs font-medium text-text-muted hover:text-cta transition-colors duration-200 px-2 py-1 rounded cursor-pointer"
          aria-label="Toggle language"
        >
          {i18n.language.startsWith('zh') ? 'EN' : 'ZH'}
        </button>
        <Link
          to="/reports"
          className="flex items-center gap-1.5 text-sm text-text-muted hover:text-cta transition-colors duration-200 cursor-pointer min-h-11 min-w-11 justify-center"
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
    <div data-testid="route-loading" className="px-4 py-12 text-center text-sm text-text-dim">
      {t('loading.page')}
    </div>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <NavBar />
        <main className="pt-20">
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
