import { CircleSlash, TriangleAlert, TrendingUp, type LucideIcon } from 'lucide-react'
import type { RecommendationType, ResearchReport } from '@/lib/types/research'

type Translate = (key: string, options?: Record<string, unknown>) => string

export interface DecisionTone {
  badgeLabel: string
  badgeClass: string
  panelClass: string
  icon: LucideIcon
  title: string
  subtitle: string
}

export function toPercent(value: number | undefined): number {
  const normalized = Number(value)
  if (!Number.isFinite(normalized)) {
    return 0
  }
  return Math.max(0, Math.min(100, Math.round(normalized * 100)))
}

export function getDecisionTone(
  recommendationType: RecommendationType,
  t: Translate,
): DecisionTone {
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

export function buildSummaryBullets(report: ResearchReport, t: Translate): string[] {
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

export function selectKeywordText(report: ResearchReport, language: string): string {
  const normalizeLanguage = (value: string | undefined): string => value?.toLowerCase().trim() ?? ''
  const uiLanguage = normalizeLanguage(language)
  const prefersChinese = uiLanguage.startsWith('zh')

  const zhKeywords = report.intent.keywords_zh.filter(Boolean)
  const enKeywords = report.intent.keywords_en.filter(Boolean)
  const preferredKeywords = prefersChinese ? zhKeywords : enKeywords
  const fallbackKeywords = prefersChinese ? enKeywords : zhKeywords

  const selected = preferredKeywords.length > 0 ? preferredKeywords : fallbackKeywords
  return selected.join(', ')
}
