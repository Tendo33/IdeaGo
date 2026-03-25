import { useId, useState } from 'react'
import { Search, Loader2, ArrowRight } from 'lucide-react'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

interface SearchBoxProps {
  onSubmit: (query: string) => void
  isLoading?: boolean
}

const MIN_QUERY_LENGTH = 5
const MAX_QUERY_LENGTH = 1000

const MIN_MEANINGFUL_CHARACTERS = 3
const MAX_SYMBOL_RATIO = 0.5

const LETTER_CHARACTER = /\p{L}/u
const ALPHANUMERIC_CHARACTER = /[\p{L}\p{N}]/u
const WHITESPACE_CHARACTER = /\s/u

type SearchValidationCode =
  | 'empty'
  | 'too_short'
  | 'too_long'
  | 'missing_letters'
  | 'low_signal'
  | 'too_many_symbols'
  | 'valid'

interface SearchQueryValidationResult {
  code: SearchValidationCode
  isValid: boolean
  normalizedQuery: string
  trimmedLength: number
}

function countCharacters(value: string, predicate: (character: string) => boolean): number {
  return Array.from(value).filter(predicate).length
}

function validateSearchQuery(query: string): SearchQueryValidationResult {
  const normalizedQuery = query.trim()
  const trimmedLength = normalizedQuery.length

  if (trimmedLength === 0) {
    return { code: 'empty', isValid: false, normalizedQuery, trimmedLength }
  }

  if (trimmedLength < MIN_QUERY_LENGTH) {
    return { code: 'too_short', isValid: false, normalizedQuery, trimmedLength }
  }

  if (trimmedLength > MAX_QUERY_LENGTH) {
    return { code: 'too_long', isValid: false, normalizedQuery, trimmedLength }
  }

  const nonWhitespaceCharacters = Array.from(normalizedQuery).filter(
    character => !WHITESPACE_CHARACTER.test(character),
  )
  const meaningfulCharacterCount = countCharacters(
    nonWhitespaceCharacters.join(''),
    character => ALPHANUMERIC_CHARACTER.test(character),
  )
  const hasLetterCharacter = nonWhitespaceCharacters.some(character => LETTER_CHARACTER.test(character))
  const symbolCharacterCount = nonWhitespaceCharacters.length - meaningfulCharacterCount
  const symbolRatio = nonWhitespaceCharacters.length === 0
    ? 0
    : symbolCharacterCount / nonWhitespaceCharacters.length

  if (!hasLetterCharacter) {
    return { code: 'missing_letters', isValid: false, normalizedQuery, trimmedLength }
  }

  if (meaningfulCharacterCount < MIN_MEANINGFUL_CHARACTERS) {
    return { code: 'low_signal', isValid: false, normalizedQuery, trimmedLength }
  }

  if (symbolRatio > MAX_SYMBOL_RATIO) {
    return { code: 'too_many_symbols', isValid: false, normalizedQuery, trimmedLength }
  }

  return { code: 'valid', isValid: true, normalizedQuery, trimmedLength }
}

function getSearchHelperText(
  validation: SearchQueryValidationResult,
  t: TFunction,
): string {
  switch (validation.code) {
    case 'empty':
      return t('search.example')
    case 'too_short':
      return t('search.tooShort', { min: MIN_QUERY_LENGTH, current: validation.trimmedLength })
    case 'too_long':
      return t('search.tooLong', { max: MAX_QUERY_LENGTH })
    case 'valid':
      return t('search.lengthCount', { current: validation.trimmedLength, max: MAX_QUERY_LENGTH })
    case 'missing_letters':
      return t('search.validation.missingLetters')
    case 'low_signal':
      return t('search.validation.lowSignal')
    case 'too_many_symbols':
      return t('search.validation.tooManySymbols')
    default:
      return t('search.example')
  }
}

function SearchBoxComponent({ onSubmit, isLoading = false }: SearchBoxProps) {
  const [query, setQuery] = useState('')
  const inputId = useId()
  const { t } = useTranslation()
  const validation = validateSearchQuery(query)
  const hasValidationError = validation.code !== 'valid' && validation.code !== 'empty'
  const isSubmitDisabled = isLoading || !validation.isValid

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (validation.isValid) {
      onSubmit(validation.normalizedQuery)
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
            aria-invalid={hasValidationError ? true : undefined}
            aria-errormessage={hasValidationError ? `${inputId}-error` : undefined}
            className="w-full h-16 border-2 border-border bg-background px-6 py-4 text-xl font-bold text-foreground placeholder:text-muted-foreground/40 transition-all duration-150 outline-none focus:ring-0 focus:border-primary focus:shadow focus:shadow-primary disabled:opacity-50 aria-invalid:border-destructive aria-invalid:focus:shadow aria-invalid:focus:shadow-destructive"
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
          className="h-16 px-8 flex items-center justify-center gap-3 bg-primary text-primary-foreground border-2 border-border font-black uppercase tracking-widest text-lg transition-all duration-150 shadow hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-sm active:translate-x-[4px] active:translate-y-[4px] active:shadow-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-x-0 disabled:hover:translate-y-0 disabled:hover:shadow cursor-pointer outline-none"
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

      <div className="mt-4 flex items-start justify-between gap-4 px-2">
        <p
          id={`${inputId}-error`}
          className={`min-w-0 flex-1 text-sm font-medium leading-5 ${hasValidationError ? 'text-destructive' : 'text-muted-foreground'}`}
          aria-live="polite"
        >
          {isLoading
            ? t('search.submittingHint')
            : getSearchHelperText(validation, t)}
        </p>

        {/* Visual brutalist decorative element */}
        <div className="hidden shrink-0 sm:flex gap-1">
          <div className="w-2 h-2 bg-primary border border-border"></div>
          <div className="w-2 h-2 bg-foreground border border-border"></div>
          <div className="w-2 h-2 bg-muted border border-border"></div>
        </div>
      </div>
    </form>
  )
}

type SearchBoxComponentType = typeof SearchBoxComponent & {
  validateQuery: typeof validateSearchQuery
}

export const SearchBox = SearchBoxComponent as SearchBoxComponentType

SearchBox.validateQuery = validateSearchQuery
