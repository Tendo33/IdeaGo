import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
  Check,
  Download,
  Link2,
  Printer,
  Share2,
  Sparkles,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ResearchReport } from '@/lib/types/research'
import { exportReport } from '@/lib/api/client'
import { buttonVariants } from '@/components/ui/Button'
import { formatAppDateTime } from '@/lib/utils/dateLocale'
import { Dropdown, DropdownItem } from './ReportHeaderMenu'
import {
  buildSummaryBullets,
  getDecisionTone,
  selectKeywordText,
  toPercent,
} from './reportHeaderUtils'

interface ReportHeaderProps {
  report: ResearchReport
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
  const keywordText = useMemo(
    () => selectKeywordText(report, language),
    [language, report],
  )

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
