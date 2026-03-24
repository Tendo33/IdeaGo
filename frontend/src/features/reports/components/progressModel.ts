import type { TFunction } from 'i18next'
import {
  parseExtractionCompletedProgressData,
  parseIntentProgressData,
  parseSourceCompletedProgressData,
  type PipelineEvent,
} from '@/lib/types/research'

export type ProgressStepStatus = 'pending' | 'active' | 'done' | 'failed' | 'cancelled'
export type ProgressStageKey = 'intent' | 'source' | 'extraction' | 'aggregation' | 'complete' | 'failed' | 'cancelled'

export interface ProgressStep {
  id: string
  label: string
  shortLabel: string
  status: ProgressStepStatus
  detail?: string
}

export interface SourcePreview {
  platform: string
  label: string
  shortLabel: string
  count?: number
  status: ProgressStepStatus
}

export interface ProgressFeedItem {
  id: string
  label: string
  tone: 'neutral' | 'live' | 'success' | 'danger' | 'muted'
}

export interface ProgressModel {
  steps: ProgressStep[]
  appType?: string
  keywords: string[]
  targetScenario?: string
  sourcePreviews: SourcePreview[]
  completedSources: number
  failedSources: number
  activeSources: number
  extractionCount: number
  aggregationCount?: number
  currentStage: ProgressStageKey
  currentTitle: string
  currentDescription: string
  focusLabel: string
  feed: ProgressFeedItem[]
}

export const DEFAULT_SOURCE_ORDER = ['github', 'tavily', 'hackernews', 'appstore', 'producthunt', 'reddit'] as const

function getDefaultSourceShortLabel(platform: string): string {
  switch (platform) {
    case 'hackernews':
      return 'HN'
    case 'producthunt':
      return 'PH'
    default:
      return platform
  }
}

export function getSourcePlatformFromEvent(event: PipelineEvent): string | null {
  const dataPlatform = event.data?.platform
  if (typeof dataPlatform === 'string' && dataPlatform.trim()) {
    return dataPlatform.trim().toLowerCase()
  }

  const stage = event.stage.trim().toLowerCase()
  if (!stage) return null
  if (stage.endsWith('_search')) {
    return stage.slice(0, -'_search'.length)
  }
  if (stage.endsWith('_extraction')) {
    return stage.slice(0, -'_extraction'.length)
  }

  const knownPlatform = DEFAULT_SOURCE_ORDER.find(platform => stage.includes(platform))
  return knownPlatform ?? null
}

function getPlatformShortLabel(t: TFunction, platform: string): string {
  return t(`report.stepper.steps.${platform}.short`, {
    defaultValue: getDefaultSourceShortLabel(platform),
  })
}

export function getPlatformLabel(t: TFunction, platform: string): string {
  return t(`report.stepper.steps.${platform}.short`, {
    defaultValue: platform,
  })
}

function deriveSteps(events: PipelineEvent[], t: TFunction): ProgressStep[] {
  const eventSourcePlatforms = events
    .map(getSourcePlatformFromEvent)
    .filter((platform): platform is string => platform !== null)
  const extraPlatforms = Array.from(
    new Set(eventSourcePlatforms.filter(platform => !DEFAULT_SOURCE_ORDER.includes(platform as (typeof DEFAULT_SOURCE_ORDER)[number]))),
  ).sort()
  const orderedPlatforms = [...DEFAULT_SOURCE_ORDER, ...extraPlatforms]

  const steps: ProgressStep[] = [
    {
      id: 'intent',
      label: t('report.stepper.steps.intent.label'),
      shortLabel: t('report.stepper.steps.intent.short'),
      status: 'pending',
    },
    ...orderedPlatforms.map(platform => ({
      id: platform,
      label: t(`report.stepper.steps.${platform}.label`, { defaultValue: platform }),
      shortLabel: getPlatformShortLabel(t, platform),
      status: 'pending' as const,
    })),
    {
      id: 'extraction',
      label: t('report.stepper.steps.extraction.label'),
      shortLabel: t('report.stepper.steps.extraction.short'),
      status: 'pending',
    },
    {
      id: 'aggregation',
      label: t('report.stepper.steps.aggregation.label'),
      shortLabel: t('report.stepper.steps.aggregation.short'),
      status: 'pending',
    },
    {
      id: 'complete',
      label: t('report.stepper.steps.complete.label'),
      shortLabel: t('report.stepper.steps.complete.short'),
      status: 'pending',
    },
  ]

  const indexByStepId = new Map(steps.map((step, index) => [step.id, index]))
  const updateStep = (stepId: string, status: ProgressStepStatus, detail?: string) => {
    const index = indexByStepId.get(stepId)
    if (index === undefined) return
    steps[index].status = status
    if (detail !== undefined) {
      steps[index].detail = detail
    }
  }

  for (const event of events) {
    switch (event.type) {
      case 'intent_started':
        updateStep('intent', 'active')
        break
      case 'intent_parsed':
        updateStep('intent', 'done')
        break
      case 'source_started': {
        const platform = getSourcePlatformFromEvent(event)
        if (platform) updateStep(platform, 'active')
        break
      }
      case 'source_completed': {
        const parsed = parseSourceCompletedProgressData(event.data)
        const platform = getSourcePlatformFromEvent(event)
        if (platform) {
          updateStep(platform, 'done', parsed.count !== undefined ? String(parsed.count) : undefined)
        }
        break
      }
      case 'source_failed': {
        const platform = getSourcePlatformFromEvent(event)
        if (platform) updateStep(platform, 'failed')
        break
      }
      case 'extraction_started':
        updateStep('extraction', 'active')
        break
      case 'extraction_completed':
        updateStep('extraction', 'done')
        break
      case 'aggregation_started':
        updateStep('aggregation', 'active')
        break
      case 'aggregation_completed':
        updateStep('aggregation', 'done')
        break
      case 'report_ready':
        updateStep('complete', 'done')
        break
      case 'error':
        updateStep('complete', 'failed')
        break
      case 'cancelled':
        updateStep('complete', 'cancelled')
        break
    }
  }

  if (events.length === 0) {
    steps[0].status = 'active'
  }

  return steps
}

function deriveCurrentStage(events: PipelineEvent[]): ProgressStageKey {
  const latestEvent = events.at(-1)
  if (!latestEvent) return 'intent'

  switch (latestEvent.type) {
    case 'intent_started':
    case 'intent_parsed':
      return 'intent'
    case 'source_started':
    case 'source_completed':
    case 'source_failed':
      return 'source'
    case 'extraction_started':
    case 'extraction_completed':
      return 'extraction'
    case 'aggregation_started':
    case 'aggregation_completed':
      return 'aggregation'
    case 'report_ready':
      return 'complete'
    case 'cancelled':
      return 'cancelled'
    case 'error':
      return 'failed'
  }
}

function describeEvent(event: PipelineEvent, t: TFunction): ProgressFeedItem {
  const platform = getSourcePlatformFromEvent(event)
  const platformLabel = platform ? getPlatformLabel(t, platform) : t('report.progress.genericSource')
  const sourceCount = parseSourceCompletedProgressData(event.data).count ?? 0
  const extractionCount = parseExtractionCompletedProgressData(event.data).count ?? 0

  switch (event.type) {
    case 'intent_started':
      return { id: `${event.timestamp}|${event.type}`, label: t('report.progress.feed.intentStarted'), tone: 'live' }
    case 'intent_parsed':
      return { id: `${event.timestamp}|${event.type}`, label: t('report.progress.feed.intentParsed'), tone: 'success' }
    case 'source_started':
      return {
        id: `${event.timestamp}|${event.type}|${platform ?? 'source'}`,
        label: t('report.progress.feed.sourceStarted', { platform: platformLabel }),
        tone: 'live',
      }
    case 'source_completed':
      return {
        id: `${event.timestamp}|${event.type}|${platform ?? 'source'}`,
        label: t('report.progress.feed.sourceCompleted', { platform: platformLabel, count: sourceCount }),
        tone: 'success',
      }
    case 'source_failed':
      return {
        id: `${event.timestamp}|${event.type}|${platform ?? 'source'}`,
        label: t('report.progress.feed.sourceFailed', { platform: platformLabel }),
        tone: 'danger',
      }
    case 'extraction_started':
      return {
        id: `${event.timestamp}|${event.type}|${platform ?? 'extraction'}`,
        label: platform
          ? t('report.progress.feed.extractionStartedPlatform', { platform: platformLabel })
          : t('report.progress.feed.extractionStarted'),
        tone: 'live',
      }
    case 'extraction_completed':
      return {
        id: `${event.timestamp}|${event.type}|${platform ?? 'extraction'}`,
        label: platform
          ? t('report.progress.feed.extractionCompletedPlatform', { platform: platformLabel, count: extractionCount })
          : t('report.progress.feed.extractionCompleted', { count: extractionCount }),
        tone: 'success',
      }
    case 'aggregation_started':
      return { id: `${event.timestamp}|${event.type}`, label: t('report.progress.feed.aggregationStarted'), tone: 'live' }
    case 'aggregation_completed':
      return {
        id: `${event.timestamp}|${event.type}`,
        label: t('report.progress.feed.aggregationCompleted', { count: extractionCount }),
        tone: 'success',
      }
    case 'report_ready':
      return { id: `${event.timestamp}|${event.type}`, label: t('report.progress.feed.reportReady'), tone: 'success' }
    case 'cancelled':
      return { id: `${event.timestamp}|${event.type}`, label: t('report.progress.feed.cancelled'), tone: 'muted' }
    case 'error':
      return { id: `${event.timestamp}|${event.type}`, label: t('report.progress.feed.error'), tone: 'danger' }
  }
}

function deriveCurrentCopy(
  stage: ProgressStageKey,
  t: TFunction,
  activePlatforms: string[],
  latestPlatform?: string | null,
): Pick<ProgressModel, 'currentTitle' | 'currentDescription' | 'focusLabel'> {
  if (stage === 'source') {
    if (activePlatforms.length > 1) {
      return {
        currentTitle: t('report.progress.current.sourceTitleMulti', { count: activePlatforms.length }),
        currentDescription: t('report.progress.current.sourceDescription'),
        focusLabel: activePlatforms.map(platform => getPlatformLabel(t, platform)).join(' / '),
      }
    }

    if (activePlatforms.length === 1 || latestPlatform) {
      const platformLabel = getPlatformLabel(t, activePlatforms[0] ?? latestPlatform ?? 'source')
      return {
        currentTitle: t('report.progress.current.sourceTitleSingle', { platform: platformLabel }),
        currentDescription: t('report.progress.current.sourceDescription'),
        focusLabel: platformLabel,
      }
    }
  }

  if (stage === 'extraction') {
    if (latestPlatform) {
      const platformLabel = getPlatformLabel(t, latestPlatform)
      return {
        currentTitle: t('report.progress.current.extractionTitleSingle', { platform: platformLabel }),
        currentDescription: t('report.progress.current.extractionDescription'),
        focusLabel: platformLabel,
      }
    }

    return {
      currentTitle: t('report.progress.current.extractionTitle'),
      currentDescription: t('report.progress.current.extractionDescription'),
      focusLabel: t('report.progress.focus.extraction'),
    }
  }

  if (stage === 'aggregation') {
    return {
      currentTitle: t('report.progress.current.aggregationTitle'),
      currentDescription: t('report.progress.current.aggregationDescription'),
      focusLabel: t('report.progress.focus.aggregation'),
    }
  }

  if (stage === 'complete') {
    return {
      currentTitle: t('report.progress.current.completeTitle'),
      currentDescription: t('report.progress.current.completeDescription'),
      focusLabel: t('report.progress.focus.complete'),
    }
  }

  if (stage === 'failed') {
    return {
      currentTitle: t('report.progress.current.failedTitle'),
      currentDescription: t('report.progress.current.failedDescription'),
      focusLabel: t('report.progress.focus.failed'),
    }
  }

  if (stage === 'cancelled') {
    return {
      currentTitle: t('report.progress.current.cancelledTitle'),
      currentDescription: t('report.progress.current.cancelledDescription'),
      focusLabel: t('report.progress.focus.cancelled'),
    }
  }

  return {
    currentTitle: t('report.progress.current.intentTitle'),
    currentDescription: t('report.progress.current.intentDescription'),
    focusLabel: t('report.progress.focus.intent'),
  }
}

export function deriveProgressModel(events: PipelineEvent[], t: TFunction): ProgressModel {
  const steps = deriveSteps(events, t)
  const latestEvent = events.at(-1) ?? null
  const appTypeState: { value?: string } = {}
  const keywordsState = new Set<string>()
  const targetScenarioState: { value?: string } = {}
  const sourceCounts = new Map<string, number>()
  let extractionCount = 0
  let aggregationCount: number | undefined

  for (const event of events) {
    if (event.type === 'intent_parsed') {
      const parsed = parseIntentProgressData(event.data)
      appTypeState.value = parsed.appType
      parsed.keywords.forEach(keyword => keywordsState.add(keyword))
      targetScenarioState.value = parsed.targetScenario
    }

    if (event.type === 'source_completed') {
      const parsed = parseSourceCompletedProgressData(event.data)
      const platform = getSourcePlatformFromEvent(event)
      if (platform) {
        sourceCounts.set(platform, parsed.count ?? 0)
      }
    }

    if (event.type === 'extraction_completed') {
      const parsed = parseExtractionCompletedProgressData(event.data)
      extractionCount += parsed.count ?? 0
    }

    if (event.type === 'aggregation_completed') {
      aggregationCount = parseExtractionCompletedProgressData(event.data).count
    }
  }

  const sourcePreviews = steps
    .filter(step => step.id !== 'intent' && step.id !== 'extraction' && step.id !== 'aggregation' && step.id !== 'complete')
    .map(step => ({
      platform: step.id,
      label: getPlatformLabel(t, step.id),
      shortLabel: step.shortLabel,
      count: sourceCounts.get(step.id),
      status: step.status,
    }))

  const activeSourcePlatforms = sourcePreviews
    .filter(source => source.status === 'active')
    .map(source => source.platform)
  const currentStage = deriveCurrentStage(events)
  const currentCopy = deriveCurrentCopy(currentStage, t, activeSourcePlatforms, latestEvent ? getSourcePlatformFromEvent(latestEvent) : null)

  return {
    steps,
    appType: appTypeState.value,
    keywords: Array.from(keywordsState),
    targetScenario: targetScenarioState.value,
    sourcePreviews,
    completedSources: sourcePreviews.filter(source => source.status === 'done').length,
    failedSources: sourcePreviews.filter(source => source.status === 'failed').length,
    activeSources: sourcePreviews.filter(source => source.status === 'active').length,
    extractionCount,
    aggregationCount,
    currentStage,
    currentTitle: currentCopy.currentTitle,
    currentDescription: currentCopy.currentDescription,
    focusLabel: currentCopy.focusLabel,
    feed: events.slice(-8).reverse().map(event => describeEvent(event, t)),
  }
}
