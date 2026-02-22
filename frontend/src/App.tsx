import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { History } from 'lucide-react'
import { HomePage } from './pages/HomePage'
import { ReportPage } from './pages/ReportPage'
import { HistoryPage } from './pages/HistoryPage'

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
        </Routes>
      </main>
    </BrowserRouter>
  )
}
