import { Alert } from '@/components/ui/Alert'
import { Button } from '@/components/ui/Button'
import { useTranslation } from 'react-i18next'
import type { ReportRuntimeStatus } from '@/lib/types/research'

interface ReportErrorBannerProps {
  message: string
  onRetry: () => void
  errorKind?: 'system' | 'runtime' | 'start_failed'
  runtimeStatus?: ReportRuntimeStatus | null
  actionLabel?: string
  actionDisabled?: boolean
  actions?: Array<{
    label: string
    onClick: () => void
    disabled?: boolean
  }>
}

function getBannerText(
  errorKind: 'system' | 'runtime' | 'start_failed',
  runtimeStatus: ReportRuntimeStatus | null | undefined,
  t: (key: string) => string,
): { title: string; retryLabel: string } {
  if (errorKind === 'start_failed') {
    return {
      title: t('report.error.systemTitle'),
      retryLabel: t('report.failed.retryShort'),
    }
  }
  if (errorKind === 'system') {
    if (runtimeStatus?.status === 'complete') {
      return {
        title: t('report.error.systemTitle'),
        retryLabel: t('report.failed.startAgain'),
      }
    }

    return {
      title: t('report.error.systemTitle'),
      retryLabel: t('report.failed.retryShort'),
    }
  }

  if (runtimeStatus?.status === 'failed') {
    return {
      title: t('report.error.failedTitle'),
      retryLabel: t('report.failed.startAgain'),
    }
  }

  if (runtimeStatus?.status === 'cancelled') {
    return {
      title: t('report.error.cancelledTitle'),
      retryLabel: t('report.failed.startAgain'),
    }
  }

  if (runtimeStatus?.status === 'not_found') {
    return {
      title: t('report.error.notFoundTitle'),
      retryLabel: t('report.failed.startAgain'),
    }
  }

  return {
    title: t('report.error.runtimeTitle'),
    retryLabel: t('report.failed.retryShort'),
  }
}

export function ReportErrorBanner({
  message,
  onRetry,
  errorKind = 'system',
  runtimeStatus,
  actionLabel,
  actionDisabled = false,
  actions,
}: ReportErrorBannerProps) {
  const { t } = useTranslation()
  const text = getBannerText(errorKind, runtimeStatus, t)
  const resolvedActions =
    actions && actions.length > 0
      ? actions
      : [{ label: actionLabel ?? text.retryLabel, onClick: onRetry, disabled: actionDisabled }]
  return (
    <Alert variant="warning" className="mb-6 items-center">
      <div className="min-w-0 flex-1">
        <p className="text-xs text-warning font-medium break-words">{text.title}</p>
        <p className="text-sm text-warning break-words whitespace-pre-wrap mt-0.5">{message}</p>
        {runtimeStatus?.error_code && (
          <p className="text-xs text-warning/80 mt-1 break-all">[{runtimeStatus.error_code}]</p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {resolvedActions.map(action => (
            <Button
              key={action.label}
              variant="outline"
              size="sm"
              onClick={action.onClick}
              disabled={action.disabled}
              aria-busy={action.disabled}
              className="border-warning text-warning hover:bg-warning/10 active:translate-x-[1px] active:translate-y-[1px] focus-visible:ring-warning transition-all"
            >
              {action.label}
            </Button>
          ))}
        </div>
      </div>
    </Alert>
  )
}
