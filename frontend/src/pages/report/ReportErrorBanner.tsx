import { AlertCircle } from 'lucide-react'

interface ReportErrorBannerProps {
  message: string
  onRetry: () => void
}

export function ReportErrorBanner({ message, onRetry }: ReportErrorBannerProps) {
  return (
    <div className="flex items-center justify-between gap-3 p-4 rounded-xl bg-danger/10 border border-danger/30 mb-6">
      <div className="flex items-center gap-3 min-w-0">
        <AlertCircle className="w-5 h-5 text-danger shrink-0" />
        <p className="text-sm text-danger">{message}</p>
      </div>
      <button
        onClick={onRetry}
        className="shrink-0 px-3 py-1.5 text-xs font-medium text-white rounded-lg bg-danger hover:bg-danger/80 cursor-pointer transition-colors duration-200"
      >
        Retry
      </button>
    </div>
  )
}
