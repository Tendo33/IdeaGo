import { Flame, Link2 } from 'lucide-react'
import type { PainSignal } from '@/lib/types/research'

export interface PainSignalsCardProps {
  signals: PainSignal[]
}

function toPercent(value: number): number {
  if (Number.isNaN(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value * 100)))
}

export function PainSignalsCard({ signals }: PainSignalsCardProps) {
  if (signals.length === 0) return null

  return (
    <div className="card h-full space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 border border-border bg-background px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
            <Flame className="h-3.5 w-3.5 text-danger" />
            Pain signals
          </div>
          <h3 className="mt-3 text-lg font-bold font-heading text-foreground">
            Recurring user friction worth solving
          </h3>
        </div>
        <div className="border border-border bg-muted/40 px-3 py-2 text-right">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
            Themes
          </p>
          <p className="mt-1 text-lg font-bold text-foreground">{signals.length}</p>
        </div>
      </div>

      <div className="space-y-4">
        {signals.slice(0, 3).map(signal => {
          const intensity = toPercent(signal.intensity)
          const frequency = toPercent(signal.frequency)
          const evidenceCount = signal.evidence_urls.length

          return (
            <div key={signal.theme} className="border-2 border-border bg-muted/35 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-base font-bold text-foreground break-words">
                    {signal.theme}
                  </p>
                  {signal.summary ? (
                    <p className="mt-1 text-sm leading-relaxed text-muted-foreground break-words">
                      {signal.summary}
                    </p>
                  ) : null}
                </div>
                <span className="shrink-0 border border-danger/25 bg-danger/10 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.14em] text-danger">
                  {intensity}% intense
                </span>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="mb-1 flex items-center justify-between gap-2 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                    <span>Intensity</span>
                    <span>{intensity}%</span>
                  </div>
                  <div className="h-2 bg-background">
                    <div
                      className="h-2 bg-danger transition-all duration-500 ease-out"
                      style={{ width: `${intensity}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="mb-1 flex items-center justify-between gap-2 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                    <span>Frequency</span>
                    <span>{frequency}%</span>
                  </div>
                  <div className="h-2 bg-background">
                    <div
                      className="h-2 bg-warning transition-all duration-500 ease-out"
                      style={{ width: `${frequency}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap gap-2">
                {signal.source_platforms.slice(0, 3).map(platform => (
                  <span
                    key={`${signal.theme}-${platform}`}
                    className="border border-border bg-background px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground"
                  >
                    {platform}
                  </span>
                ))}
                {evidenceCount > 0 ? (
                  <span className="inline-flex items-center gap-1 border border-border bg-background px-2.5 py-1 text-[11px] font-medium text-foreground">
                    <Link2 className="h-3 w-3 text-muted-foreground" />
                    {evidenceCount} evidence links
                  </span>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
