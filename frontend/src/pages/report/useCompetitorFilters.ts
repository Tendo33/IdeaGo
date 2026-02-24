import { useCallback, useMemo, useState } from 'react'
import type { Platform, ResearchReport } from '../../types/research'

export type SortKey = 'relevance' | 'name' | 'sources'
export type ViewMode = 'grid' | 'list'

export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'relevance', label: 'Relevance' },
  { value: 'name', label: 'Name' },
  { value: 'sources', label: 'Sources' },
]

export const PLATFORM_OPTIONS: Platform[] = ['github', 'tavily', 'hackernews']

export function useCompetitorFilters(report: ResearchReport | null) {
  const [sortBy, setSortBy] = useState<SortKey>('relevance')
  const [platformFilter, setPlatformFilter] = useState<Set<Platform>>(new Set())
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [compareSet, setCompareSet] = useState<Set<string>>(new Set())
  const [showCompare, setShowCompare] = useState(false)

  const filteredCompetitors = useMemo(() => {
    if (!report) return []

    let list = [...report.competitors]
    if (platformFilter.size > 0) {
      list = list.filter(competitor => competitor.source_platforms.some(platform => platformFilter.has(platform)))
    }

    switch (sortBy) {
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
  }, [platformFilter, report, sortBy])

  const compareCompetitors = useMemo(() => {
    if (!report) return []
    return report.competitors.filter(competitor => compareSet.has(competitor.name))
  }, [compareSet, report])

  const togglePlatform = useCallback((platform: Platform) => {
    setPlatformFilter(previous => {
      const next = new Set(previous)
      if (next.has(platform)) {
        next.delete(platform)
      } else {
        next.add(platform)
      }
      return next
    })
  }, [])

  const toggleCompare = useCallback((name: string) => {
    setCompareSet(previous => {
      const next = new Set(previous)
      if (next.has(name)) {
        next.delete(name)
      } else if (next.size < 4) {
        next.add(name)
      }
      return next
    })
  }, [])

  const clearCompare = useCallback(() => {
    setCompareSet(new Set())
    setShowCompare(false)
  }, [])

  return {
    sortBy,
    setSortBy,
    platformFilter,
    togglePlatform,
    viewMode,
    setViewMode,
    filteredCompetitors,
    compareSet,
    toggleCompare,
    compareCompetitors,
    showCompare,
    setShowCompare,
    clearCompare,
    setCompareSet,
  }
}
