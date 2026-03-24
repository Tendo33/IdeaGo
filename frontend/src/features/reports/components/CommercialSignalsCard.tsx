import { BanknoteArrowUp, Wallet } from 'lucide-react'
import type { CommercialSignal } from '@/lib/types/research'

export interface CommercialSignalsCardProps {
  signals: CommercialSignal[]
}

function toPercent(value: number): number {
  if (Number.isNaN(value)) return 0
  return Math.max(0, Math.min(100, Math.round(value * 100)))
}

export function CommercialSignalsCard({ signals }: CommercialSignalsCardProps) {
  if (signals.length === 0) return null

  return (
    <div className="card h-full space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 border border-border bg-background px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
            <Wallet className="h-3.5 w-3.5 text-cta" />
            Commercial signals
          </div>
          <h3 className="mt-3 text-lg font-bold font-heading text-foreground">
            Demand cues that suggest paid intent
          </h3>
        </div>
        <div className="border border-border bg-muted/40 px-3 py-2 text-right">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
            Signals
          </p>
          <p className="mt-1 text-lg font-bold text-foreground">{signals.length}</p>
        </div>
      </div>

      <div className="space-y-4">
        {signals.slice(0, 3).map(signal => {
          const intent = toPercent(signal.intent_strength)

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
                <span className="shrink-0 border border-cta/25 bg-cta/10 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.14em] text-cta">
                  {intent}% intent
                </span>
              </div>

              <div className="mt-4">
                <div className="mb-1 flex items-center justify-between gap-2 text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                  <span>Commercial strength</span>
                  <span>{intent}%</span>
                </div>
                <div className="h-2 bg-background">
                  <div
                    className="h-2 bg-cta transition-all duration-500 ease-out"
                    style={{ width: `${intent}%` }}
                  />
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
                <div className="min-w-0">
                  <p className="text-[11px] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                    Monetization hint
                  </p>
                  <p className="mt-1 text-sm text-foreground break-words">
                    {signal.monetization_hint || 'Commercial demand is visible, but packaging is still undefined.'}
                  </p>
                </div>
                {signal.source_platforms.length > 0 ? (
                  <div className="flex flex-wrap gap-2 sm:justify-end">
                    {signal.source_platforms.slice(0, 3).map(platform => (
                      <span
                        key={`${signal.theme}-${platform}`}
                        className="inline-flex items-center gap-1 border border-border bg-background px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.08em] text-muted-foreground"
                      >
                        <BanknoteArrowUp className="h-3 w-3 text-cta" />
                        {platform}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
