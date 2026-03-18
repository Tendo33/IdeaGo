interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-muted border-2 border-border shadow-[4px_4px_0px_0px_var(--border)] ${className}`}
      aria-hidden="true"
    />
  )
}

export function ReportCardSkeleton() {
  return (
    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-2 border-border bg-card p-5 shadow-[4px_4px_0px_0px_var(--border)]">
      <div className="mr-6 min-w-0 flex-1 mb-4 sm:mb-0 space-y-3 w-full">
        <Skeleton className="h-6 w-3/4 shadow-[2px_2px_0px_0px_var(--border)]" />
        <div className="flex items-center gap-4">
          <Skeleton className="h-4 w-24 shadow-[2px_2px_0px_0px_var(--border)]" />
          <Skeleton className="h-4 w-20 shadow-[2px_2px_0px_0px_var(--border)]" />
        </div>
      </div>
      <Skeleton className="h-10 w-10 shrink-0 shadow-[2px_2px_0px_0px_var(--border)]" />
    </div>
  )
}

export function CompetitorCardSkeleton() {
  return (
    <div className="p-6 md:p-8 bg-card border-2 border-border shadow-[6px_6px_0px_0px_var(--border)] space-y-4">
      <div className="flex items-start justify-between">
        <div className="space-y-3 flex-1">
          <Skeleton className="h-6 w-1/2 shadow-[2px_2px_0px_0px_var(--border)]" />
          <Skeleton className="h-4 w-3/4 shadow-[2px_2px_0px_0px_var(--border)]" />
        </div>
        <Skeleton className="h-12 w-12 shrink-0 shadow-[2px_2px_0px_0px_var(--border)]" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-8 w-20 shadow-[2px_2px_0px_0px_var(--border)]" />
        <Skeleton className="h-8 w-24 shadow-[2px_2px_0px_0px_var(--border)]" />
        <Skeleton className="h-8 w-16 shadow-[2px_2px_0px_0px_var(--border)]" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-4 w-full shadow-[2px_2px_0px_0px_var(--border)]" />
        <Skeleton className="h-4 w-5/6 shadow-[2px_2px_0px_0px_var(--border)]" />
      </div>
    </div>
  )
}
