import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getCompetitorDomIdFromId, getCompetitorId } from '../competitor'
import type { Competitor } from '../types/research'
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
  const [containerHeight, setContainerHeight] = useState(DEFAULT_VIEWPORT_HEIGHT)
  const [containerWidth, setContainerWidth] = useState(0)

  const columns = viewMode === 'grid' && containerWidth >= 640 ? 2 : 1
  const estimatedRowHeight =
    viewMode === 'grid' ? ESTIMATED_GRID_ROW_HEIGHT + 24 : ESTIMATED_LIST_ROW_HEIGHT + 16
  const rowCount = Math.ceil(competitors.length / columns)
  const gridClassName = columns === 2 ? 'grid gap-6 grid-cols-2 pb-6' : 'grid gap-6 grid-cols-1 pb-6'
  const competitorSignature = useMemo(
    () => createCompetitorSignature(competitors),
    [competitors],
  )
  const resetKey = `${viewMode}:${columns}:${competitorSignature}`
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

  const createRowRef = useCallback(
    (rowIndex: number) => (node: HTMLDivElement | null) => {
      if (!node) return
      const nextHeight = Math.ceil(node.getBoundingClientRect().height)
      if (nextHeight <= 0) return
      setMeasuredHeights(previous => {
        const base = previous.key === resetKey ? previous.values : {}
        if (base[rowIndex] === nextHeight && previous.key === resetKey) return previous
        return { key: resetKey, values: { ...base, [rowIndex]: nextHeight } }
      })
    },
    [resetKey],
  )

  return (
    <div
      ref={scrollRef}
      className="max-h-[68vh] min-h-[380px] overflow-auto pr-1"
      onScroll={event => {
        const nextScrollTop = event.currentTarget.scrollTop
        setScrollState(previous => {
          if (previous.key === resetKey && previous.value === nextScrollTop) return previous
          return { key: resetKey, value: nextScrollTop }
        })
      }}
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        {visibleRows.map(rowIndex => {
          const rowStart = rowIndex * columns
          const rowItems = competitors.slice(rowStart, rowStart + columns)
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
                <div className={gridClassName}>
                  {rowItems.map((competitor, itemIndex) => {
                    const competitorId = getCompetitorId(competitor)
                    let originalIndex = -1
                    if (allCompetitors) {
                      originalIndex = allCompetitors.findIndex(c => getCompetitorId(c) === competitorId)
                    }
                    const rank = originalIndex >= 0 ? originalIndex + 1 : rowStart + itemIndex + 1
                    
                    return (
                      <CompetitorCard
                        key={competitorId}
                        competitor={competitor}
                        rank={rank}
                        domId={getCompetitorDomIdFromId(competitorId)}
                        variant={originalIndex === 0 ? 'featured' : (originalIndex === -1 && rank === 1 ? 'featured' : 'standard')}
                        compareSelected={compareSet.has(competitorId)}
                        onToggleCompare={() => onToggleCompare(competitorId)}
                      />
                    )
                  })}
                </div>
              ) : (
                <div className="pb-4">
                  {rowItems.map((competitor, itemIndex) => {
                    const competitorId = getCompetitorId(competitor)
                    let originalIndex = -1
                    if (allCompetitors) {
                      originalIndex = allCompetitors.findIndex(c => getCompetitorId(c) === competitorId)
                    }
                    const rank = originalIndex >= 0 ? originalIndex + 1 : rowStart + itemIndex + 1
                    
                    return (
                      <CompetitorRow
                        key={competitorId}
                        competitor={competitor}
                        rank={rank}
                        domId={getCompetitorDomIdFromId(competitorId)}
                        compareSelected={compareSet.has(competitorId)}
                        onToggleCompare={() => onToggleCompare(competitorId)}
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
