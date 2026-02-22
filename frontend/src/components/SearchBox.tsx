import { useState } from 'react'
import { Search, Loader2 } from 'lucide-react'

interface SearchBoxProps {
  onSubmit: (query: string) => void
  isLoading?: boolean
}

export function SearchBox({ onSubmit, isLoading = false }: SearchBoxProps) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (trimmed.length >= 5) {
      onSubmit(trimmed)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Describe your startup idea..."
          disabled={isLoading}
          className="w-full px-5 py-4 pr-14 text-lg rounded-xl border border-border bg-bg-card text-text placeholder-text-dim transition-colors duration-200 focus:outline-none focus:border-cta focus:ring-2 focus:ring-cta/20 disabled:opacity-50"
          aria-label="Startup idea description"
        />
        <button
          type="submit"
          disabled={isLoading || query.trim().length < 5}
          className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 rounded-lg bg-cta text-white cursor-pointer transition-colors duration-200 hover:bg-cta-hover disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-cta/50"
          aria-label="Start research"
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Search className="w-5 h-5" />
          )}
        </button>
      </div>
      <p className="mt-2 text-sm text-text-dim text-center">
        e.g. "A browser extension that converts web pages to Markdown notes"
      </p>
    </form>
  )
}
