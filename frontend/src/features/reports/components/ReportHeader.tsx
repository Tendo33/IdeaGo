import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  Check,
  ChevronDown,
  CircleSlash,
  Download,
  Link2,
  Printer,
  Share2,
  Sparkles,
  TriangleAlert,
  TrendingUp,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { RecommendationType, ResearchReport } from '@/lib/types/research'
import { exportReport } from '@/lib/api/client'
import { buttonVariants } from '@/components/ui/Button'

interface ReportHeaderProps {
  report: ResearchReport
}

function Dropdown({
  trigger,
  children,
}: {
  trigger: React.ReactNode
  children: React.ReactNode
}) {
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return

    function handleClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKeyDown)

    const firstMenuItem = ref.current?.querySelector<HTMLElement>('[role="menuitem"]')
    firstMenuItem?.focus()

    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        ref={triggerRef}
        onClick={() => setOpen(current => !current)}
        className={buttonVariants({
          variant: 'secondary',
          size: 'sm',
          className: 'justify-between gap-1 px-3',
        })}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
      >
        <span className="inline-flex min-w-0 items-center gap-1.5">{trigger}</span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200 ease-out-quint ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 top-[calc(100%+4px)] z-50 mt-0 w-48 overflow-hidden rounded-none border-2 border-border bg-popover/95 py-1.5 shadow backdrop-blur-2xl outline-none animate-in fade-in slide-in-from-top-2 duration-200 ease-out-quint"
          onClick={event => {
            if ((event.target as HTMLElement).closest('[role="menuitem"]')) {
              setOpen(false)
            }
          }}
          tabIndex={-1}
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}

function DropdownItem({
  icon: Icon,
  label,
  onClick,
  href,
}: {
  icon: typeof Download
  label: string
  onClick?: () => void
  href?: string
}) {
  const cls = buttonVariants({
    variant: 'ghost',
    size: 'sm',
    className: 'w-full justify-start gap-2.5 px-3.5 text-left normal-case tracking-normal',
  })

  if (href) {
    return (
      <a href={href} download className={cls} role="menuitem">
        <Icon className="h-4 w-4 shrink-0" />
        {label}
      </a>
    )
  }

  return (
    <button type="button" onClick={onClick} className={cls} role="menuitem" tabIndex={0}>
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </button>
  )
}

function toPercent(value: number | undefined): number {
  const normalized = Number(value)
  if (!Number.isFinite(normalized)) {
    return 0
  }
  return Math.max(0, Math.min(100, Math.round(normalized * 100)))
}

function getDecisionTone(
  recommendationType: RecommendationType,
): {
  badgeLabel: string
  badgeClass: string
  panelClass: string
  icon: typeof TrendingUp
  title: string
  subtitle: string
} {
  if (recommendationType === 'no_go') {
    return {
      badgeLabel: 'No-go',
      badgeClass: 'border-danger/30 bg-danger/10 text-danger',
      panelClass: 'border-danger/20 bg-linear-to-br from-danger/10 via-card to-card',
      icon: CircleSlash,
      title: 'Should we build this? Probably not yet.',
      subtitle: 'The current evidence suggests the opportunity is weak or poorly timed.',
    }
  }
  if (recommendationType === 'caution') {
    return {
      badgeLabel: 'Caution',
      badgeClass: 'border-warning/30 bg-warning/10 text-warning',
      panelClass: 'border-warning/20 bg-linear-to-br from-warning/10 via-card to-card',
      icon: TriangleAlert,
      title: 'Should we build this? Only with a narrow wedge.',
      subtitle: 'There is signal here, but the entry point needs to be disciplined.',
    }
  }
  return {
    badgeLabel: 'Go',
    badgeClass: 'border-cta/30 bg-cta/10 text-cta',
    panelClass: 'border-cta/20 bg-linear-to-br from-cta/10 via-card to-card',
    icon: TrendingUp,
    title: 'Should we build this? Yes, if we stay focused.',
    subtitle: 'The opportunity looks real enough to justify moving forward with a sharp wedge.',
  }
}

function buildSummaryBullets(report: ResearchReport): string[] {
  const bullets = [
    report.whitespace_opportunities[0]?.wedge
      ? `Best entry wedge: ${report.whitespace_opportunities[0].wedge}`
      : '',
    report.pain_signals[0]?.theme ? `Main pain: ${report.pain_signals[0].theme}` : '',
    report.commercial_signals[0]?.theme
      ? `Commercial cue: ${report.commercial_signals[0].theme}`
      : '',
    report.differentiation_angles[0]
      ? `Execution angle: ${report.differentiation_angles[0]}`
      : '',
  ]

  return bullets.filter(Boolean).slice(0, 3)
}

export function ReportHeader({ report }: ReportHeaderProps) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState<string | null>(null)
  const feedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(
    () => () => {
      if (feedbackTimerRef.current) {
        clearTimeout(feedbackTimerRef.current)
      }
    },
    [],
  )

  const decisionTone = useMemo(
    () => getDecisionTone(report.recommendation_type),
    [report.recommendation_type],
  )
  const DecisionIcon = decisionTone.icon
  const opportunityPercent = toPercent(report.opportunity_score?.score)
  const summaryBullets = useMemo(() => buildSummaryBullets(report), [report])

  const handleCopyLink = async () => {
    if (feedbackTimerRef.current) {
      clearTimeout(feedbackTimerRef.current)
      feedbackTimerRef.current = null
    }
    setCopyError(null)

    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API unavailable')
      }
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      feedbackTimerRef.current = setTimeout(() => {
        setCopied(false)
        feedbackTimerRef.current = null
      }, 2000)
    } catch {
      setCopied(false)
      setCopyError(t('report.header.copyFailed'))
      feedbackTimerRef.current = setTimeout(() => {
        setCopyError(null)
        feedbackTimerRef.current = null
      }, 3000)
    }
  }

  return (
    <div className="mb-8 flex flex-col gap-5">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div className="min-w-0 flex-1">
          <Link
            to="/"
            className={buttonVariants({
              variant: 'ghost',
              size: 'sm',
              className: 'mb-3 w-fit gap-1.5 px-1 text-muted-foreground hover:text-cta',
            })}
          >
            <ArrowLeft className="h-4 w-4" />
            {t('report.header.newSearch')}
          </Link>
          <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
            Decision-first research report
          </p>
          <h1 className="mt-2 break-words text-3xl font-bold font-heading text-foreground">
            {report.query}
          </h1>
          <p className="mt-2 break-words text-sm leading-relaxed text-muted-foreground">
            {report.intent.app_type} · {report.intent.target_scenario} ·{' '}
            <span className="whitespace-nowrap">
              {new Date(report.created_at).toLocaleString()}
            </span>
          </p>
        </div>

        <div className="no-print mt-2 flex w-full shrink-0 items-center gap-2 md:mt-0 md:w-auto">
          <Dropdown
            trigger={
              <>
                <Share2 className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="hidden sm:inline">{t('report.header.share')}</span>
              </>
            }
          >
            <DropdownItem
              icon={copied ? Check : Link2}
              label={copied ? t('report.header.copied') : t('report.header.copyLink')}
              onClick={handleCopyLink}
            />
          </Dropdown>
          <Dropdown
            trigger={
              <>
                <Download className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="hidden sm:inline">{t('report.header.export')}</span>
              </>
            }
          >
            <DropdownItem
              icon={Download}
              label={t('report.header.markdown')}
              onClick={() => exportReport(report.id)}
            />
            <DropdownItem
              icon={Printer}
              label={t('report.header.print')}
              onClick={() => window.print()}
            />
          </Dropdown>
        </div>
      </div>

      {copyError ? <p className="text-xs text-danger">{copyError}</p> : null}

      <section className={`card overflow-hidden ${decisionTone.panelClass}`}>
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.9fr)]">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-3">
              <span
                className={`inline-flex items-center gap-2 border px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] ${decisionTone.badgeClass}`}
              >
                <DecisionIcon className="h-3.5 w-3.5" />
                {decisionTone.badgeLabel}
              </span>
              <span className="inline-flex items-center gap-2 border border-border bg-background/85 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5 text-cta" />
                Opportunity score {opportunityPercent}%
              </span>
            </div>

            <div className="space-y-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                  Should we build this?
                </p>
                <h2 className="mt-2 text-2xl font-bold font-heading text-foreground">
                  {decisionTone.title}
                </h2>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {decisionTone.subtitle}
              </p>
              <p className="text-base leading-relaxed text-foreground break-words">
                {report.go_no_go || report.market_summary}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="border-2 border-border bg-background/80 p-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Pain themes
                </p>
                <p className="mt-2 text-2xl font-bold text-foreground">
                  {report.pain_signals.length}
                </p>
              </div>
              <div className="border-2 border-border bg-background/80 p-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Commercial cues
                </p>
                <p className="mt-2 text-2xl font-bold text-foreground">
                  {report.commercial_signals.length}
                </p>
              </div>
              <div className="border-2 border-border bg-background/80 p-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Whitespace wedges
                </p>
                <p className="mt-2 text-2xl font-bold text-foreground">
                  {report.whitespace_opportunities.length}
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col justify-between border-2 border-border bg-background/75 p-5">
            <div>
              <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Why this call
              </p>
              <div className="mt-4 space-y-3">
                {summaryBullets.length > 0 ? (
                  summaryBullets.map(item => (
                    <div
                      key={item}
                      className="border border-border bg-muted/45 px-3 py-3 text-sm text-foreground"
                    >
                      {item}
                    </div>
                  ))
                ) : (
                  <p className="text-sm leading-relaxed text-muted-foreground">
                    Signal extraction is still sparse, so use the recommendation
                    with extra caution.
                  </p>
                )}
              </div>
            </div>
            <div className="mt-5 border-t-2 border-border pt-4 text-sm text-muted-foreground">
              <p className="font-semibold text-foreground">Context keywords</p>
              <p className="mt-2 leading-relaxed break-words">
                {report.intent.keywords_en.join(', ')}
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
