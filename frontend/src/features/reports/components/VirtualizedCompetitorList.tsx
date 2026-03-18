import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getCompetitorDomIdFromId, getCompetitorId } from '../competitor'
import type { Competitor } from '@/lib/types/research'
import { CompetitorCard } from './CompetitorCard'
import { CompetitorRow } from './CompetitorRow'

const OVERSCAN_ROWS = 3
const ESTIMATED_LIST_ROW_HEIGHT = 82
const ESTIMATED_GRID_ROW_HEIGHT = 360
const DEFAULT_VIEWPORT_HEIGHT = 640

type ViewMode = 'grid' | 'list'

interface VirtualizedCompetitorListProps {
  competitors: Competitor[]
  allCompetitors?: Competitor[]
  viewMode: ViewMode
  compareSet: Set<string>
  onToggleCompare: (competitorId: string) => void
}

interface ScrollState {
  key: string
  value: number
}

interface MeasuredHeightsState {
  key: string
  values: Record<number, number>
}

function binarySearchOffset(offsets: number[], target: number): number {
  let low = 0
  let high = offsets.length - 2
  while (low <= high) {
    const mid = Math.floor((low + high) / 2)
    const current = offsets[mid]
    const next = offsets[mid + 1]
    if (current <= target && target < next) {
      return mid
    }
    if (current > target) {
      high = mid - 1
    } else {
      low = mid + 1
    }
  }
  return Math.max(0, Math.min(offsets.length - 2, low))
}

function createCompetitorSignature(competitors: Competitor[]): string {
  let hash = 2166136261
  for (const competitor of competitors) {
    const competitorId = getCompetitorId(competitor)
    for (let index = 0; index < competitorId.length; index += 1) {
      hash ^= competitorId.charCodeAt(index)
      hash = Math.imul(hash, 16777619)
    }
  }
  return `${competitors.length}:${(hash >>> 0).toString(36)}`
}

export function VirtualizedCompetitorList({
  competitors,
  allCompetitors,
  viewMode,
  compareSet,
  onToggleCompare,
}: VirtualizedCompetitorListProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const scrollRafRef = useRef<number | null>(null)
  const lastScrollTopRef = useRef(0)
  const [containerHeight, setContainerHeight] = useState(DEFAULT_VIEWPORT_HEIGHT)
  const [containerWidth, setContainerWidth] = useState(0)

  const columns = viewMode === 'grid' && containerWidth >= 640 ? 2 : 1
  const estimatedRowHeight =
    viewMode === 'grid' ? ESTIMATED_GRID_ROW_HEIGHT + 24 : ESTIMATED_LIST_ROW_HEIGHT + 16
  const gridClassName = columns === 2 ? 'grid gap-6 grid-cols-2 pb-6' : 'grid gap-6 grid-cols-1 pb-6'

  // Detect if the first competitor in the current list is the globally-ranked #1 (featured)
  const hasFeaturedFirst = useMemo(() => {
    if (viewMode !== 'grid' || competitors.length === 0) return false
    const source = allCompetitors ?? competitors
    if (source.length === 0) return false
    return getCompetitorId(competitors[0]) === getCompetitorId(source[0])
  }, [viewMode, competitors, allCompetitors])

  // When featured card is first, row 0 holds it alone; remaining competitors fill 2-col rows
  const rowCount = useMemo(() => {
    if (hasFeaturedFirst) return 1 + Math.ceil((competitors.length - 1) / columns)
    return Math.ceil(competitors.length / columns)
  }, [hasFeaturedFirst, competitors.length, columns])

  const competitorSignature = useMemo(
    () => createCompetitorSignature(competitors),
    [competitors],
  )
  const resetKey = `${viewMode}:${columns}:${competitorSignature}:${hasFeaturedFirst ? 'f' : 'n'}`
  const [scrollState, setScrollState] = useState<ScrollState>(() => ({ key: resetKey, value: 0 }))
  const [measuredHeights, setMeasuredHeights] = useState<MeasuredHeightsState>(() => ({
    key: resetKey,
    values: {},
  }))
  const effectiveScrollTop = useMemo(
    () => (scrollState.key === resetKey ? scrollState.value : 0),
    [resetKey, scrollState],
  )
  const effectiveMeasuredHeights = useMemo(
    () => (measuredHeights.key === resetKey ? measuredHeights.values : {}),
    [measuredHeights, resetKey],
  )
  const competitorRankById = useMemo(() => {
    const source = allCompetitors ?? competitors
    const map = new Map<string, number>()
    for (let index = 0; index < source.length; index += 1) {
      map.set(getCompetitorId(source[index]), index + 1)
    }
    return map
  }, [allCompetitors, competitors])

  useEffect(() => {
    const node = scrollRef.current
    if (!node) return

    const updateSize = () => {
      setContainerHeight(node.clientHeight || DEFAULT_VIEWPORT_HEIGHT)
      setContainerWidth(node.clientWidth || 0)
    }

    updateSize()
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateSize)
      return () => window.removeEventListener('resize', updateSize)
    }

    const observer = new ResizeObserver(updateSize)
    observer.observe(node)
    return () => observer.disconnect()
  }, [resetKey])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0
    }
  }, [resetKey])

  useEffect(() => {
    return () => {
      if (scrollRafRef.current !== null) {
        cancelAnimationFrame(scrollRafRef.current)
        scrollRafRef.current = null
      }
    }
  }, [])

  const offsets = useMemo(() => {
    const values = new Array(rowCount + 1).fill(0)
    for (let index = 0; index < rowCount; index += 1) {
      const rowHeight = effectiveMeasuredHeights[index] ?? estimatedRowHeight
      values[index + 1] = values[index] + rowHeight
    }
    return values
  }, [effectiveMeasuredHeights, estimatedRowHeight, rowCount])

  const totalHeight = offsets[rowCount] ?? 0
  const visibleRange = useMemo(() => {
    if (rowCount === 0) {
      return { startRow: 0, endRow: -1 }
    }
    const start = binarySearchOffset(offsets, Math.max(0, effectiveScrollTop))
    const end = binarySearchOffset(offsets, effectiveScrollTop + containerHeight)
    return {
      startRow: Math.max(0, start - OVERSCAN_ROWS),
      endRow: Math.min(rowCount - 1, end + OVERSCAN_ROWS),
    }
  }, [containerHeight, effectiveScrollTop, offsets, rowCount])

  const visibleRows = useMemo(() => {
    if (visibleRange.endRow < visibleRange.startRow) return []
    return Array.from(
      { length: visibleRange.endRow - visibleRange.startRow + 1 },
      (_, index) => visibleRange.startRow + index,
    )
  }, [visibleRange.endRow, visibleRange.startRow])

  const rowObservers = useRef(new Map<number, ResizeObserver>())

  const createRowRef = useCallback(
    (rowIndex: number) => (node: HTMLDivElement | null) => {
      const observers = rowObservers.current
      if (observers.has(rowIndex)) {
        observers.get(rowIndex)?.disconnect()
        observers.delete(rowIndex)
      }

      if (!node) return

      const updateHeight = () => {
        const nextHeight = Math.ceil(node.getBoundingClientRect().height)
        if (nextHeight <= 0) return
        setMeasuredHeights(previous => {
          const base = previous.key === resetKey ? previous.values : {}
          if (base[rowIndex] === nextHeight && previous.key === resetKey) return previous
          return { key: resetKey, values: { ...base, [rowIndex]: nextHeight } }
        })
      }

      updateHeight()

      if (typeof ResizeObserver !== 'undefined') {
        const observer = new ResizeObserver(updateHeight)
        observer.observe(node)
        observers.set(rowIndex, observer)
      }
    },
    [resetKey],
  )

  useEffect(() => {
    return () => {
      rowObservers.current.forEach(obs => obs.disconnect())
      rowObservers.current.clear()
    }
  }, [])

  return (
    <div
      ref={scrollRef}
      className="max-h-[68vh] min-h-[380px] overflow-auto px-2 py-2"
      onScroll={event => {
        lastScrollTopRef.current = event.currentTarget.scrollTop
        if (scrollRafRef.current !== null) return
        scrollRafRef.current = requestAnimationFrame(() => {
          const nextScrollTop = lastScrollTopRef.current
          setScrollState(previous => {
            if (previous.key === resetKey && previous.value === nextScrollTop) return previous
            return { key: resetKey, value: nextScrollTop }
          })
          scrollRafRef.current = null
        })
      }}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        {visibleRows.map(rowIndex => {
          // Resolve which competitors belong to this row
          let rowItems: typeof competitors
          if (hasFeaturedFirst) {
            if (rowIndex === 0) {
              rowItems = [competitors[0]]
            } else {
              const offset = 1 + (rowIndex - 1) * columns
              rowItems = competitors.slice(offset, offset + columns)
            }
          } else {
            const rowStart = rowIndex * columns
            rowItems = competitors.slice(rowStart, rowStart + columns)
          }

          // Row 0 of a featured-first layout always uses a single-column grid
          const rowGridClass =
            hasFeaturedFirst && rowIndex === 0
              ? 'grid gap-6 grid-cols-1 pb-6'
              : columns === 2 && rowItems.length === 1
                ? 'grid gap-6 grid-cols-1 pb-6'
                : gridClassName

          return (
            <div
              key={`row-${rowIndex}`}
              ref={createRowRef(rowIndex)}
              style={{
                position: 'absolute',
                top: offsets[rowIndex],
                left: 0,
                right: 0,
              }}
            >
              {viewMode === 'grid' ? (
                <div className={rowGridClass}>
                  {rowItems.map((competitor, itemIndex) => {
                    const competitorId = getCompetitorId(competitor)
                    const rank = competitorRankById.get(competitorId) ?? (itemIndex + 1)
                    const originalIndex = rank - 1

                    return (
                      <CompetitorCard
                        key={competitorId}
                        competitor={competitor}
                        rank={rank}
                        domId={getCompetitorDomIdFromId(competitorId)}
                        variant={originalIndex === 0 ? 'featured' : 'standard'}
                        compareSelected={compareSet.has(competitorId)}
                        onToggleCompare={onToggleCompare}
                      />
                    )
                  })}
                </div>
              ) : (
                <div className="pb-4">
                  {rowItems.map((competitor, itemIndex) => {
                    const competitorId = getCompetitorId(competitor)
                    const rank = competitorRankById.get(competitorId) ?? (itemIndex + 1)

                    return (
                      <CompetitorRow
                        key={competitorId}
                        competitor={competitor}
                        rank={rank}
                        domId={getCompetitorDomIdFromId(competitorId)}
                        compareSelected={compareSet.has(competitorId)}
                        onToggleCompare={onToggleCompare}
                      />
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
