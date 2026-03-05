interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded-lg bg-muted/65 ${className}`}
      aria-hidden="true"
    />
  )
}

export function ReportCardSkeleton() {
  return (
    <div className="flex items-center justify-between px-4 py-4 rounded-xl bg-card/85 border border-border/80 backdrop-blur-md">
      <div className="min-w-0 flex-1 mr-4 space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <div className="flex items-center gap-4">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
      <Skeleton className="h-8 w-8 rounded-lg" />
    </div>
  )
}

export function CompetitorCardSkeleton() {
  return (
    <div className="p-5 rounded-2xl bg-card/85 border border-border/80 backdrop-blur-xl space-y-3">
      <div className="flex items-start justify-between">
        <div className="space-y-2 flex-1">
          <Skeleton className="h-5 w-1/2" />
          <Skeleton className="h-3 w-3/4" />
        </div>
        <Skeleton className="h-10 w-10 rounded-full shrink-0" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-6 w-16 rounded-full" />
        <Skeleton className="h-6 w-20 rounded-full" />
        <Skeleton className="h-6 w-14 rounded-full" />
      </div>
      <div className="space-y-1.5">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />
      </div>
    </div>
  )
}
