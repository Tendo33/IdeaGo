import { useTranslation } from 'react-i18next'

export interface CompareFloatingBarProps {
  count: number
  onCompare: () => void
  onClear: () => void
}

export function CompareFloatingBar({ count, onCompare, onClear }: CompareFloatingBarProps) {
  const { t } = useTranslation()
  if (count < 2) return null

  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-4 px-6 py-3.5 rounded-none bg-popover/95 border-2 border-border shadow-[4px_4px_0px_0px_var(--border)] animate-fade-in no-print">
      <span className="text-sm text-foreground">
        <span className="font-semibold text-cta">{count}</span> {t('report.compare.selected')}
      </span>
      <button
        type="button"
        onClick={() => {
          onCompare()
          setTimeout(() => {
            document.getElementById('compare-panel')?.scrollIntoView({ behavior: 'smooth' })
          }, 50)
        }}
        className="px-5 py-2 text-sm font-semibold rounded-none bg-cta text-primary-foreground cursor-pointer transition-all duration-300 hover:bg-cta-hover hover:shadow-[4px_4px_0px_0px_var(--border)] hover:-translate-y-px focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
      >
        {t('report.compare.compareBtn')}
      </button>
      <button
        type="button"
        onClick={onClear}
        className="text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 rounded-none px-1"
      >
        {t('report.compare.clear')}
      </button>
    </div>
  )
}
