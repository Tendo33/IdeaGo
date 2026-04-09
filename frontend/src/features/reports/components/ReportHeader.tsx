import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowLeft,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ResearchReport } from '@/lib/types/research'
import { buttonVariants } from '@/components/ui/Button'
import { formatAppDateTime } from '@/lib/utils/dateLocale'
import { ReportDecisionHero } from '@/features/reports/components/ReportDecisionHero'
import { ReportHeaderActionsMenu } from '@/features/reports/components/ReportHeaderActionsMenu'

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

        <ReportHeaderActionsMenu
          reportId={report.id}
          copied={copied}
          onCopyLink={handleCopyLink}
        />
      </div>

      {copyError ? <p className="text-xs text-danger">{copyError}</p> : null}
      <ReportDecisionHero report={report} keywordText={keywordText} />
    </div>
  )
}
