interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-muted border-2 border-border shadow ${className}`}
      aria-hidden="true"
    />
  )
}

export function CompetitorCardSkeleton() {
  return (
    <div className="p-6 md:p-8 bg-card border-2 border-border shadow-md space-y-4">
      <div className="flex items-start justify-between">
        <div className="space-y-3 flex-1">
          <Skeleton className="h-6 w-1/2 shadow-sm" />
          <Skeleton className="h-4 w-3/4 shadow-sm" />
        </div>
        <Skeleton className="h-12 w-12 shrink-0 shadow-sm" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-8 w-20 shadow-sm" />
        <Skeleton className="h-8 w-24 shadow-sm" />
        <Skeleton className="h-8 w-16 shadow-sm" />
      </div>
      <div className="space-y-2">
        <Skeleton className="h-4 w-full shadow-sm" />
        <Skeleton className="h-4 w-5/6 shadow-sm" />
      </div>
    </div>
  )
}
