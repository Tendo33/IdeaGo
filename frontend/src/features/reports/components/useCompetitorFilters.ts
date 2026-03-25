import { useCallback, useMemo, useState, type SetStateAction } from 'react'
import { getCompetitorId } from '@/features/reports/competitor'
import type { Platform, ResearchReport } from '@/lib/types/research'

export type SortKey = 'relevance' | 'name' | 'sources'
export type ViewMode = 'grid' | 'list'

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'name', label: 'Name' },
  { value: 'sources', label: 'Sources' },
]

export const PLATFORM_OPTIONS: Platform[] = ["github", "tavily", "hackernews", "appstore", "producthunt", "reddit"];

interface CompetitorFilterState {
  reportId: string | null
  sortBy: SortKey
  platformFilter: Set<Platform>
  viewMode: ViewMode
  compareSet: Set<string>
  showCompare: boolean
}

function createDefaultState(reportId: string | null): CompetitorFilterState {
  return {
    reportId,
    sortBy: 'relevance',
    platformFilter: new Set(),
    viewMode: 'grid',
    compareSet: new Set(),
    showCompare: false,
  }
}

export function useCompetitorFilters(report: ResearchReport | null) {
  const reportId = report?.id ?? null
  const [state, setState] = useState<CompetitorFilterState>(() => createDefaultState(reportId))

  const activeState = useMemo(
    () => (state.reportId === reportId ? state : createDefaultState(reportId)),
    [reportId, state],
  )

  const updateState = useCallback(
    (updater: (previous: CompetitorFilterState) => CompetitorFilterState) => {
      setState(previous => {
        const scoped = previous.reportId === reportId ? previous : createDefaultState(reportId)
        return updater(scoped)
      })
    },
    [reportId],
  )

  const setSortBy = useCallback(
    (nextValue: SetStateAction<SortKey>) => {
      updateState(previous => ({
        ...previous,
        sortBy: typeof nextValue === 'function' ? nextValue(previous.sortBy) : nextValue,
      }))
    },
    [updateState],
  )

  const setViewMode = useCallback(
    (nextValue: SetStateAction<ViewMode>) => {
      updateState(previous => ({
        ...previous,
        viewMode: typeof nextValue === 'function' ? nextValue(previous.viewMode) : nextValue,
      }))
    },
    [updateState],
  )

  const setShowCompare = useCallback(
    (nextValue: SetStateAction<boolean>) => {
      updateState(previous => ({
        ...previous,
        showCompare: typeof nextValue === 'function' ? nextValue(previous.showCompare) : nextValue,
      }))
    },
    [updateState],
  )

  const setCompareSet = useCallback(
    (nextValue: SetStateAction<Set<string>>) => {
      updateState(previous => ({
        ...previous,
        compareSet: typeof nextValue === 'function' ? nextValue(previous.compareSet) : nextValue,
      }))
    },
    [updateState],
  )

  const filteredCompetitors = useMemo(() => {
    if (!report) return []

    let list = [...report.competitors]
    if (activeState.platformFilter.size > 0) {
      list = list.filter(competitor =>
        competitor.source_platforms.some(platform => activeState.platformFilter.has(platform)),
      )
    }

    switch (activeState.sortBy) {
      case 'name':
        list.sort((a, b) => a.name.localeCompare(b.name))
        break
      case 'sources':
        list.sort((a, b) => b.source_platforms.length - a.source_platforms.length)
        break
      default:
        list.sort((a, b) => b.relevance_score - a.relevance_score)
        break
    }

    return list
  }, [activeState.platformFilter, activeState.sortBy, report])

  const compareCompetitors = useMemo(() => {
    if (!report) return []
    return report.competitors.filter(competitor => activeState.compareSet.has(getCompetitorId(competitor)))
  }, [activeState.compareSet, report])

  const togglePlatform = useCallback((platform: Platform) => {
    updateState(previous => {
      const next = new Set(previous.platformFilter)
      if (next.has(platform)) {
        next.delete(platform)
      } else {
        next.add(platform)
      }
      return { ...previous, platformFilter: next }
    })
  }, [updateState])

  const toggleCompare = useCallback((competitorId: string) => {
    updateState(previous => {
      const next = new Set(previous.compareSet)
      if (next.has(competitorId)) {
        next.delete(competitorId)
      } else if (next.size < 4) {
        next.add(competitorId)
      }
      return { ...previous, compareSet: next }
    })
  }, [updateState])

  const clearCompare = useCallback(() => {
    updateState(previous => ({ ...previous, compareSet: new Set(), showCompare: false }))
  }, [updateState])

  return {
    sortBy: activeState.sortBy,
    setSortBy,
    platformFilter: activeState.platformFilter,
    togglePlatform,
    viewMode: activeState.viewMode,
    setViewMode,
    filteredCompetitors,
    compareSet: activeState.compareSet,
    toggleCompare,
    compareCompetitors,
    showCompare: activeState.showCompare,
    setShowCompare,
    clearCompare,
    setCompareSet,
  }
}
