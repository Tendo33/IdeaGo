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
      <div className="relative group">
        <input
          id={inputId}
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder={t('search.placeholder')}
          maxLength={MAX_QUERY_LENGTH}
          disabled={isLoading}
          aria-disabled={isLoading}
          className="w-full rounded-none border-b-2 border-border bg-transparent px-2 py-4 pr-14 text-xl font-medium text-foreground placeholder:text-muted-foreground/60 transition-colors duration-300 outline-none focus:border-primary disabled:opacity-50"
          aria-label={t('search.placeholder')}
        />
        <button
          type="submit"
          disabled={isSubmitDisabled}
          aria-live="polite"
          className="absolute right-0 top-1/2 -translate-y-1/2 p-3 text-muted-foreground outline-none transition-all duration-300 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
          aria-label={t('search.button')}
        >
          {isLoading ? (
            <Loader2 className="w-6 h-6 animate-spin text-primary" />
          ) : (
            <Search className="w-6 h-6" />
          )}
        </button>
      </div>
      <p className="mt-3 text-xs text-text-dim text-left px-2 font-mono" aria-live="polite">
        {isLoading
          ? t('search.submittingHint')
          : isQueryTooLong
            ? t('search.tooLong', { max: MAX_QUERY_LENGTH })
            : isQueryTooShort && trimmedLength > 0
              ? t('search.tooShort', { min: MIN_QUERY_LENGTH, current: trimmedLength })
              : trimmedLength > 0
                ? t('search.lengthCount', { current: trimmedLength, max: MAX_QUERY_LENGTH })
                : t('search.example')}
      </p>
    </form>
  )
}
