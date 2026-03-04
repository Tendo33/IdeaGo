import { useId, useState } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface SearchBoxProps {
  onSubmit: (query: string) => void
  isLoading?: boolean
}

const MIN_QUERY_LENGTH = 5
const MAX_QUERY_LENGTH = 1000

export function SearchBox({ onSubmit, isLoading = false }: SearchBoxProps) {
  const [query, setQuery] = useState('')
  const inputId = useId()
  const { t } = useTranslation()
  const trimmedLength = query.trim().length
  const isQueryTooShort = trimmedLength < MIN_QUERY_LENGTH
  const isQueryTooLong = trimmedLength > MAX_QUERY_LENGTH
  const isSubmitDisabled = isLoading || isQueryTooShort || isQueryTooLong

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (trimmed.length >= MIN_QUERY_LENGTH && trimmed.length <= MAX_QUERY_LENGTH) {
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
          maxLength={MAX_QUERY_LENGTH}
          disabled={isLoading}
          className="w-full rounded-2xl border border-white/10 bg-black/40 backdrop-blur-md px-5 py-4 pr-14 text-lg text-text placeholder-text-dim shadow-2xl transition-all duration-300 outline-none focus:border-cta focus:ring-1 focus:ring-cta/30 focus:bg-black/80 disabled:opacity-50 hover:border-white/20"
          aria-label={t('search.placeholder')}
        />
        <button
          type="submit"
          disabled={isSubmitDisabled}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-xl bg-cta p-2.5 text-bg outline-none transition-all duration-300 hover:bg-cta-hover hover:shadow-[0_0_15px_rgba(251,191,36,0.5)] hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer focus:ring-1 focus:ring-cta/50"
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
        {isLoading
          ? t('search.submittingHint')
          : isQueryTooLong
            ? t('search.tooLong', { max: MAX_QUERY_LENGTH })
            : isQueryTooShort
              ? t('search.tooShort', { min: MIN_QUERY_LENGTH, current: trimmedLength })
              : t('search.lengthCount', { current: trimmedLength, max: MAX_QUERY_LENGTH })}
      </p>
      <p className="mt-1 text-sm text-text-dim text-center">{t('search.example')}</p>
    </form>
  )
}
