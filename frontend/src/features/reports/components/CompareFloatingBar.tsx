import { useTranslation } from 'react-i18next'
import { buttonVariants } from '@/components/ui/Button'

export interface CompareFloatingBarProps {
  count: number
  onCompare: () => void
  onClear: () => void
}

export function CompareFloatingBar({ count, onCompare, onClear }: CompareFloatingBarProps) {
  const { t } = useTranslation()
  if (count < 2) return null

  return (
    <div className="fixed bottom-4 left-1/2 z-40 flex w-[min(calc(100%-1.5rem),32rem)] -translate-x-1/2 flex-wrap items-center justify-center gap-3 rounded-none border-2 border-border bg-popover/95 px-4 py-3 shadow animate-fade-in no-print sm:bottom-6 sm:w-auto sm:max-w-none sm:flex-nowrap sm:justify-between sm:gap-4 sm:px-6 sm:py-3.5">
      <span className="text-center text-sm text-foreground sm:text-left">
        <span className="font-semibold text-cta">{count}</span> {t('report.compare.selected')}
      </span>
      <button
        type="button"
        onClick={onCompare}
        className={buttonVariants({ variant: 'primary', size: 'sm', className: 'w-full px-5 sm:w-auto' })}
      >
        {t('report.compare.compareBtn')}
      </button>
      <button
        type="button"
        onClick={onClear}
        className={buttonVariants({ variant: 'ghost', size: 'sm', className: 'px-1 text-xs normal-case tracking-normal' })}
      >
        {t('report.compare.clear')}
      </button>
    </div>
  )
}
