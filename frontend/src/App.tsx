import { BrowserRouter, Routes, Route, Link, useNavigate } from 'react-router-dom'
import { History, ArrowLeft } from 'lucide-react'
import { HomePage } from './pages/HomePage'
import { ReportPage } from './pages/ReportPage'
import { HistoryPage } from './pages/HistoryPage'

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
  )
}
