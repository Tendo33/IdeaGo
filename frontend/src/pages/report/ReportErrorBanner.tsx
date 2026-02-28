import { AlertCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ReportRuntimeStatus } from '../../types/research'

interface ReportErrorBannerProps {
  message: string
  onRetry: () => void
  errorKind?: 'system' | 'runtime'
  runtimeStatus?: ReportRuntimeStatus | null
}

function getBannerText(
  errorKind: 'system' | 'runtime',
  runtimeStatus: ReportRuntimeStatus | null | undefined,
  t: (key: string) => string,
): { title: string; retryLabel: string } {
  if (errorKind === 'system') {
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
      retryLabel: t('report.failed.retryShort'),
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
}: ReportErrorBannerProps) {
  const { t } = useTranslation()
  const text = getBannerText(errorKind, runtimeStatus, t)
  return (
    <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-danger/10 border border-danger/30 mb-6">
      <div className="flex items-center gap-3 min-w-0">
        <AlertCircle className="w-5 h-5 text-danger shrink-0" />
        <div className="min-w-0">
          <p className="text-xs text-danger font-medium">{text.title}</p>
          <p className="text-sm text-danger">{message}</p>
          {runtimeStatus?.error_code && (
            <p className="text-xs text-danger/80 mt-0.5">[{runtimeStatus.error_code}]</p>
          )}
        </div>
      </div>
      <button
        onClick={onRetry}
        className="shrink-0 px-3 py-1.5 text-xs font-medium text-white rounded-lg bg-danger hover:bg-danger/80 cursor-pointer transition-colors duration-200"
      >
        {text.retryLabel}
      </button>
    </div>
  )
}
