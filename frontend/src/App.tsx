import { Component, type ReactNode, type ErrorInfo } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import { History, ArrowLeft, AlertTriangle } from 'lucide-react'
import { HomePage } from './pages/HomePage'
import { ReportPage } from './pages/ReportPage'
import { HistoryPage } from './pages/HistoryPage'

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center px-4 bg-bg">
          <div className="max-w-md text-center">
            <AlertTriangle className="w-12 h-12 text-warning mx-auto mb-4" />
            <h1 className="text-2xl font-bold font-[family-name:var(--font-heading)] text-text mb-2">
              Something went wrong
            </h1>
            <p className="text-sm text-text-muted mb-6">
              {this.state.error?.message ?? 'An unexpected error occurred.'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null })
                window.location.href = '/'
              }}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cta text-white hover:bg-cta-hover transition-colors duration-200 cursor-pointer"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Home
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function NotFound() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <h1 className="text-6xl font-bold font-[family-name:var(--font-heading)] text-text-dim mb-4">404</h1>
      <p className="text-lg text-text-muted mb-6">Page not found</p>
      <button
        onClick={() => navigate('/')}
        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-cta text-white hover:bg-cta-hover transition-colors duration-200 cursor-pointer"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Home
      </button>
    </div>
  )
}

function NavBar() {
  return (
    <nav className="fixed top-4 left-4 right-4 z-50 flex items-center justify-between px-5 py-3 rounded-xl bg-bg-card/80 backdrop-blur-md border border-border">
      <Link
        to="/"
        className="text-lg font-bold font-[family-name:var(--font-heading)] text-text cursor-pointer hover:text-cta transition-colors duration-200"
      >
        Idea<span className="text-cta">Go</span>
      </Link>
      <Link
        to="/reports"
        className="flex items-center gap-1.5 text-sm text-text-muted hover:text-cta transition-colors duration-200 cursor-pointer"
      >
        <History className="w-4 h-4" />
        History
      </Link>
    </nav>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <NavBar />
        <main className="pt-20">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/reports/:id" element={<ReportPage />} />
            <Route path="/reports" element={<HistoryPage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
