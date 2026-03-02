import { useId, useState } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface SearchBoxProps {
  onSubmit: (query: string) => void
  isLoading?: boolean
}

export function SearchBox({ onSubmit, isLoading = false }: SearchBoxProps) {
  const [query, setQuery] = useState('')
  const inputId = useId()
  const { t } = useTranslation()

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (trimmed.length >= 5) {
      onSubmit(trimmed)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <label htmlFor={inputId} className="sr-only">
        {t('search.placeholder')}
      </label>
      <div className="relative">
        <input
          id={inputId}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder={t('search.placeholder')}
          disabled={isLoading}
          className="w-full rounded-2xl border border-border bg-bg-card px-5 py-4 pr-14 text-lg text-text placeholder-text-dim shadow-[0_16px_30px_-26px_rgba(16,24,40,0.55)] transition-all duration-200 outline-none focus:border-primary focus:ring-3 focus:ring-primary/20 disabled:opacity-50 hover:border-primary/25"
          aria-label={t('search.placeholder')}
        />
        <button
          type="submit"
          disabled={isLoading || query.trim().length < 5}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-xl bg-cta p-2.5 text-white outline-none transition-all duration-200 hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer focus:ring-2 focus:ring-primary/50"
          aria-label={t('search.button')}
        >
          {isLoading ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <Search className="w-5 h-5" />
          )}
        </button>
      </div>
      <p className="mt-2 text-sm text-text-dim text-center">
        {t('search.example')}
      </p>
    </form>
  )
}
