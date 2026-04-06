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
import { formatAppDateTime } from '@/lib/utils/dateLocale'

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
  const menuRef = useRef<HTMLDivElement>(null)
  const initialFocusRef = useRef<'first' | 'last'>('first')

  const getMenuItems = () => {
    const menu = menuRef.current
    if (!menu) return []
    return Array.from(
      menu.querySelectorAll<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])'),
    )
  }

  const focusMenuItem = (index: number) => {
    const items = getMenuItems()
    if (items.length === 0) return
    const next = (index + items.length) % items.length
    items[next]?.focus()
  }

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

    const menuItems = getMenuItems()
    if (menuItems.length > 0) {
      const initialIndex = initialFocusRef.current === 'last' ? menuItems.length - 1 : 0
      menuItems[initialIndex]?.focus()
    }

    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const onTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      initialFocusRef.current = 'first'
      setOpen(true)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      initialFocusRef.current = 'last'
      setOpen(true)
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      initialFocusRef.current = 'first'
      setOpen(true)
    }
  }

  const onMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const menuItems = getMenuItems()
    if (menuItems.length === 0) return
    const focusedIndex = menuItems.findIndex(item => item === document.activeElement)
    const currentIndex = focusedIndex >= 0 ? focusedIndex : 0

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusMenuItem(currentIndex + 1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusMenuItem(currentIndex - 1)
      return
    }
    if (event.key === 'Home') {
      event.preventDefault()
      focusMenuItem(0)
      return
    }
    if (event.key === 'End') {
      event.preventDefault()
      focusMenuItem(menuItems.length - 1)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
      return
    }
    if (event.key === 'Tab') {
      setOpen(false)
    }
  }

  return (
    <div className="relative" ref={ref}>
      <button
        ref={triggerRef}
        onClick={() => setOpen(current => !current)}
        onKeyDown={onTriggerKeyDown}
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
          className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200 ease-out ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          ref={menuRef}
          className="absolute right-0 top-[calc(100%+4px)] z-50 mt-0 w-48 rounded-none border-2 border-border bg-popover/95 py-1.5 shadow backdrop-blur-2xl outline-none animate-fade-in"
          onKeyDown={onMenuKeyDown}
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
  t: (key: string, options?: Record<string, unknown>) => string,
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
      badgeLabel: t('report.header.decision.badge.noGo'),
      badgeClass: 'border-danger/30 bg-danger/10 text-danger',
      panelClass: 'border-danger/20 bg-linear-to-br from-danger/10 via-card to-card',
      icon: CircleSlash,
      title: t('report.header.decision.title.noGo'),
      subtitle: t('report.header.decision.subtitle.noGo'),
    }
  }
  if (recommendationType === 'caution') {
    return {
      badgeLabel: t('report.header.decision.badge.caution'),
      badgeClass: 'border-warning/30 bg-warning/10 text-warning',
      panelClass: 'border-warning/20 bg-linear-to-br from-warning/10 via-card to-card',
      icon: TriangleAlert,
      title: t('report.header.decision.title.caution'),
      subtitle: t('report.header.decision.subtitle.caution'),
    }
  }
  return {
    badgeLabel: t('report.header.decision.badge.go'),
    badgeClass: 'border-cta/30 bg-cta/10 text-cta',
    panelClass: 'border-cta/20 bg-linear-to-br from-cta/10 via-card to-card',
    icon: TrendingUp,
    title: t('report.header.decision.title.go'),
    subtitle: t('report.header.decision.subtitle.go'),
  }
}

function buildSummaryBullets(
  report: ResearchReport,
  t: (key: string, options?: Record<string, unknown>) => string,
): string[] {
  const bullets = [
    report.whitespace_opportunities[0]?.wedge
      ? t('report.header.summary.bestEntryWedge', { value: report.whitespace_opportunities[0].wedge })
      : '',
    report.pain_signals[0]?.theme
      ? t('report.header.summary.mainPain', { value: report.pain_signals[0].theme })
      : '',
    report.commercial_signals[0]?.theme
      ? t('report.header.summary.commercialCue', { value: report.commercial_signals[0].theme })
      : '',
    report.differentiation_angles[0]
      ? t('report.header.summary.executionAngle', { value: report.differentiation_angles[0] })
      : '',
  ]

  return bullets.filter(Boolean).slice(0, 3)
}

export function ReportHeader({ report }: ReportHeaderProps) {
  const { t, i18n } = useTranslation()
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
    () => getDecisionTone(report.recommendation_type, t),
    [report.recommendation_type, t],
  )
  const DecisionIcon = decisionTone.icon
  const opportunityPercent = toPercent(report.opportunity_score?.score)
  const summaryBullets = useMemo(() => buildSummaryBullets(report, t), [report, t])
  const language = i18n.resolvedLanguage ?? i18n.language
  const keywordText = useMemo(() => {
    const normalizeLanguage = (value: string | undefined): string =>
      value?.toLowerCase().trim() ?? ''
    const uiLanguage = normalizeLanguage(i18n.resolvedLanguage ?? i18n.language)
    const prefersChinese = uiLanguage.startsWith('zh')

    const zhKeywords = report.intent.keywords_zh.filter(Boolean)
    const enKeywords = report.intent.keywords_en.filter(Boolean)
    const preferredKeywords = prefersChinese ? zhKeywords : enKeywords
    const fallbackKeywords = prefersChinese ? enKeywords : zhKeywords

    const selected = preferredKeywords.length > 0 ? preferredKeywords : fallbackKeywords
    return selected.join(', ')
  }, [i18n.language, i18n.resolvedLanguage, report.intent.keywords_en, report.intent.keywords_zh])

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
            {t('report.header.chromeLabel')}
          </p>
          <h1 className="mt-2 break-words text-3xl font-bold font-heading text-foreground">
            {report.query}
          </h1>
          <p className="mt-2 break-words text-sm leading-relaxed text-muted-foreground">
            {report.intent.app_type} · {report.intent.target_scenario} ·{' '}
            <span className="whitespace-nowrap">
              {formatAppDateTime(report.created_at, language)}
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

      <section className={`card ${decisionTone.panelClass}`}>
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
                {t('report.header.opportunityScore', { value: opportunityPercent })}
              </span>
            </div>

            <div className="space-y-3">
              <div>
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                  {t('report.sections.shouldWeBuildThis')}
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
                  {t('report.header.metrics.painThemes')}
                </p>
                <p className="mt-2 text-2xl font-bold text-foreground">
                  {report.pain_signals.length}
                </p>
              </div>
              <div className="border-2 border-border bg-background/80 p-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  {t('report.header.metrics.commercialCues')}
                </p>
                <p className="mt-2 text-2xl font-bold text-foreground">
                  {report.commercial_signals.length}
                </p>
              </div>
              <div className="border-2 border-border bg-background/80 p-4">
                <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  {t('report.header.metrics.whitespaceWedges')}
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
                {t('report.header.whyThisCall')}
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
                    {t('report.header.summary.sparse')}
                  </p>
                )}
              </div>
            </div>
            <div className="mt-5 border-t-2 border-border pt-4 text-sm text-muted-foreground">
              <p className="font-semibold text-foreground">{t('report.header.contextKeywords')}</p>
              <p className="mt-2 leading-relaxed break-words">
                {keywordText}
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
