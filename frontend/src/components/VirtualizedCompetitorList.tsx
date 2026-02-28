import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { getCompetitorId } from '../competitor'
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
  viewMode: ViewMode
  compareSet: Set<string>
  onToggleCompare: (competitorId: string) => void
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

export function VirtualizedCompetitorList({
  competitors,
  viewMode,
  compareSet,
  onToggleCompare,
}: VirtualizedCompetitorListProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [containerHeight, setContainerHeight] = useState(DEFAULT_VIEWPORT_HEIGHT)
  const [containerWidth, setContainerWidth] = useState(0)
  const [scrollTop, setScrollTop] = useState(0)
  const [measuredHeights, setMeasuredHeights] = useState<Record<number, number>>({})

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
  }, [])

  const columns = viewMode === 'grid' && containerWidth >= 1024 ? 2 : 1
  const estimatedRowHeight =
    viewMode === 'grid' ? ESTIMATED_GRID_ROW_HEIGHT : ESTIMATED_LIST_ROW_HEIGHT
  const rowCount = Math.ceil(competitors.length / columns)

  const offsets = useMemo(() => {
    const values = new Array(rowCount + 1).fill(0)
    for (let index = 0; index < rowCount; index += 1) {
      const rowHeight = measuredHeights[index] ?? estimatedRowHeight
      values[index + 1] = values[index] + rowHeight
    }
    return values
  }, [estimatedRowHeight, measuredHeights, rowCount])

  const totalHeight = offsets[rowCount] ?? 0
  const visibleRange = useMemo(() => {
    if (rowCount === 0) {
      return { startRow: 0, endRow: -1 }
    }
    const start = binarySearchOffset(offsets, Math.max(0, scrollTop))
    const end = binarySearchOffset(offsets, scrollTop + containerHeight)
    return {
      startRow: Math.max(0, start - OVERSCAN_ROWS),
      endRow: Math.min(rowCount - 1, end + OVERSCAN_ROWS),
    }
  }, [containerHeight, offsets, rowCount, scrollTop])

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
        if (previous[rowIndex] === nextHeight) return previous
        return { ...previous, [rowIndex]: nextHeight }
      })
    },
    [],
  )

  return (
    <div
      ref={scrollRef}
      className="max-h-[68vh] min-h-[380px] overflow-auto pr-1"
      onScroll={event => setScrollTop(event.currentTarget.scrollTop)}
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
                <div className="grid gap-4 sm:grid-cols-1 lg:grid-cols-2">
                  {rowItems.map((competitor, itemIndex) => {
                    const rank = rowStart + itemIndex + 1
                    const competitorId = getCompetitorId(competitor)
                    return (
                      <CompetitorCard
                        key={competitorId}
                        competitor={competitor}
                        rank={rank}
                        variant={rank === 1 ? 'featured' : 'standard'}
                        compareSelected={compareSet.has(competitorId)}
                        onToggleCompare={() => onToggleCompare(competitorId)}
                      />
                    )
                  })}
                </div>
              ) : (
                <div className="space-y-2">
                  {rowItems.map((competitor, itemIndex) => {
                    const rank = rowStart + itemIndex + 1
                    const competitorId = getCompetitorId(competitor)
                    return (
                      <CompetitorRow
                        key={competitorId}
                        competitor={competitor}
                        rank={rank}
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
