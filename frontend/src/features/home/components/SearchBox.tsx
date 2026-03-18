import { useId, useState } from 'react'
import { Search, Loader2, ArrowRight } from 'lucide-react'
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
    <form onSubmit={handleSubmit} className="w-full">
      <label htmlFor={inputId} className="sr-only">
        {t('search.placeholder')}
      </label>

      <div className="relative flex flex-col md:flex-row gap-4 items-stretch">
        <div className="relative flex-1">
          <input
            id={inputId}
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={t('search.placeholder')}
            maxLength={MAX_QUERY_LENGTH}
            disabled={isLoading}
            aria-disabled={isLoading}
            aria-invalid={isQueryTooLong || (isQueryTooShort && trimmedLength > 0) ? true : undefined}
            aria-errormessage={isQueryTooLong || (isQueryTooShort && trimmedLength > 0) ? `${inputId}-error` : undefined}
            className="w-full h-16 border-2 border-border bg-background px-6 py-4 text-xl font-bold text-foreground placeholder:text-muted-foreground/40 transition-all duration-150 outline-none focus:ring-0 focus:border-primary focus:shadow-[4px_4px_0px_0px_var(--primary)] disabled:opacity-50 aria-invalid:border-destructive aria-invalid:focus:shadow-[4px_4px_0px_0px_var(--destructive)]"
            aria-label={t('search.placeholder')}
          />
          <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground/30">
            <Search className="w-6 h-6" />
          </div>
        </div>

        <button
          type="submit"
          disabled={isSubmitDisabled}
          aria-live="polite"
          className="h-16 px-8 flex items-center justify-center gap-3 bg-primary text-primary-foreground border-2 border-border font-black uppercase tracking-widest text-lg transition-all duration-150 shadow-[4px_4px_0px_0px_var(--border)] hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] active:translate-x-[4px] active:translate-y-[4px] active:shadow-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:shadow-[4px_4px_0px_0px_var(--border)] cursor-pointer outline-none"
          aria-label={t('search.button')}
        >
          {isLoading ? (
            <Loader2 className="w-6 h-6 animate-spin" />
          ) : (
            <>
              {t('search.button')}
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
      </div>

      <div className="mt-4 flex items-center justify-between px-2">
        <p id={`${inputId}-error`} className={`text-xs font-mono font-bold uppercase tracking-wider ${isQueryTooLong || (isQueryTooShort && trimmedLength > 0) ? 'text-destructive' : 'text-muted-foreground'}`} aria-live="polite">
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

        {/* Visual brutalist decorative element */}
        <div className="hidden sm:flex gap-1">
          <div className="w-2 h-2 bg-primary border border-border"></div>
          <div className="w-2 h-2 bg-foreground border border-border"></div>
          <div className="w-2 h-2 bg-muted border border-border"></div>
        </div>
      </div>
    </form>
  )
}
