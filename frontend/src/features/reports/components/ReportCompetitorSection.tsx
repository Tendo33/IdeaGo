import { useId, type ReactNode } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowUpDown, LayoutGrid, List, type LucideIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { CompetitorCard } from '@/features/reports/components/CompetitorCard'
import { CompetitorRow } from '@/features/reports/components/CompetitorRow'
import { VirtualizedCompetitorList } from '@/features/reports/components/VirtualizedCompetitorList'
import { getCompetitorDomIdFromId, getCompetitorId } from '@/features/reports/competitor'
import type { Platform, ResearchReport } from '@/lib/types/research'
import type { SortKey, ViewMode } from './useCompetitorFilters'
import { PLATFORM_OPTIONS, SORT_OPTIONS } from './useCompetitorFilters'

const cardStagger = {
  hidden: { opacity: 0, y: 16 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: index * 0.06, duration: 0.4, ease: [0.25, 1, 0.5, 1] as const },
  }),
}

const VIRTUALIZATION_THRESHOLD = 35

interface ReportCompetitorSectionProps {
  allCompetitors: ResearchReport['competitors']
  filteredCompetitors: ResearchReport['competitors']
  compareSet: Set<string>
  sortBy: SortKey
  setSortBy: (sortKey: SortKey) => void
  platformFilter: Set<Platform>
  togglePlatform: (platform: Platform) => void
  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void
  toggleCompare: (competitorId: string) => void
  competitorRankById: Map<string, number>
}

interface ViewModeToggleButtonProps {
  icon: LucideIcon
  active: boolean
  ariaLabel: string
  onClick: () => void
}

function ViewModeToggleButton({ icon: Icon, active, ariaLabel, onClick }: ViewModeToggleButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`rounded-none min-w-[44px] min-h-[44px] flex items-center justify-center cursor-pointer transition-colors focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset ${active ? 'filter-chip-active' : 'text-muted-foreground hover:text-foreground'}`}
      aria-label={ariaLabel}
      aria-pressed={active}
    >
      <Icon className="w-3.5 h-3.5" />
    </button>
  )
}

export function ReportCompetitorSection({
  allCompetitors,
  filteredCompetitors,
  compareSet,
  sortBy,
  setSortBy,
  platformFilter,
  togglePlatform,
  viewMode,
  setViewMode,
  toggleCompare,
  competitorRankById,
}: ReportCompetitorSectionProps) {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const shouldAnimateCards = !reduceMotion && filteredCompetitors.length <= 20
  const shouldUseVirtualization = filteredCompetitors.length >= VIRTUALIZATION_THRESHOLD
  const sortSelectId = useId()
  const sortLabel = t('report.sort.label', { defaultValue: 'Sort by' })

  const renderCardWrapper = (key: string, index: number, margin: string, child: ReactNode) => {
    if (!shouldAnimateCards) {
      return <div key={key}>{child}</div>
    }
    return (
      <motion.div
        key={key}
        custom={index}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin }}
        variants={cardStagger}
      >
        {child}
      </motion.div>
    )
  }

  return (
    <section id="section-competitors">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold font-heading text-foreground">
          {t('report.competitors.title', { count: filteredCompetitors.length, total: allCompetitors.length })}
        </h2>
        <div className="flex flex-wrap items-center gap-2">
          <div className="interactive-surface flex items-center mr-1">
            <ViewModeToggleButton
              icon={LayoutGrid}
              active={viewMode === 'grid'}
              ariaLabel={t('report.competitors.gridView')}
              onClick={() => setViewMode('grid')}
            />
            <ViewModeToggleButton
              icon={List}
              active={viewMode === 'list'}
              ariaLabel={t('report.competitors.listView')}
              onClick={() => setViewMode('list')}
            />
          </div>

          {PLATFORM_OPTIONS.map(platform => (
            <button
              key={platform}
              onClick={() => togglePlatform(platform)}
              className={`filter-chip px-2.5 py-1 ${platformFilter.has(platform) ? 'filter-chip-active' : ''} focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2`}
              aria-pressed={platformFilter.has(platform)}
            >
              {platform}
            </button>
          ))}

          <div className="interactive-surface flex items-center gap-1 ml-1 rounded-none px-2 py-1 focus-within:ring-2 focus-within:ring-primary focus-within:ring-offset-2">
            <ArrowUpDown className="w-3.5 h-3.5 text-muted-foreground" />
            <label htmlFor={sortSelectId} className="sr-only">
              {sortLabel}
            </label>
            <select
              id={sortSelectId}
              value={sortBy}
              onChange={event => setSortBy(event.target.value as SortKey)}
              className="text-xs bg-transparent text-muted-foreground border-none outline-none cursor-pointer appearance-none pr-1 focus:outline-none"
            >
              {SORT_OPTIONS.map(option => (
                <option key={option.value} value={option.value}>
                  {t(`report.sort.${option.value}`)}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {shouldUseVirtualization && (
        <p className="text-xs text-muted-foreground mb-3">{t('report.competitors.virtualizedHint')}</p>
      )}

      {viewMode === 'grid' &&
        (shouldUseVirtualization ? (
          <VirtualizedCompetitorList
            competitors={filteredCompetitors}
            allCompetitors={allCompetitors}
            viewMode="grid"
            compareSet={compareSet}
            onToggleCompare={toggleCompare}
          />
        ) : (() => {
          const firstId = filteredCompetitors.length > 0 ? getCompetitorId(filteredCompetitors[0]) : null
          const firstRank = firstId != null ? (competitorRankById.get(firstId) ?? 1) : 1
          const isFeaturedFirst = firstRank === 1
          const featuredCompetitor = isFeaturedFirst ? filteredCompetitors[0] : null
          const restCompetitors = isFeaturedFirst ? filteredCompetitors.slice(1) : filteredCompetitors

          return (
            <>
              {featuredCompetitor && (() => {
                const competitorId = getCompetitorId(featuredCompetitor)
                return renderCardWrapper(
                  competitorId,
                  0,
                  '-30px',
                  <CompetitorCard
                    competitor={featuredCompetitor}
                    rank={1}
                    domId={getCompetitorDomIdFromId(competitorId)}
                    variant="featured"
                    compareSelected={compareSet.has(competitorId)}
                    onToggleCompare={toggleCompare}
                  />,
                )
              })()}
              <div className="grid gap-4 md:grid-cols-2">
                {restCompetitors.map((competitor, index) => {
                  const competitorId = getCompetitorId(competitor)
                  const domId = getCompetitorDomIdFromId(competitorId)
                  const rank = competitorRankById.get(competitorId) ?? (index + 2)
                  return renderCardWrapper(
                    competitorId,
                    isFeaturedFirst ? index + 1 : index,
                    '-30px',
                    <CompetitorCard
                      competitor={competitor}
                      rank={rank}
                      domId={domId}
                      variant="standard"
                      compareSelected={compareSet.has(competitorId)}
                      onToggleCompare={toggleCompare}
                    />,
                  )
                })}
              </div>
            </>
          )
        })())}

      {viewMode === 'list' &&
        (shouldUseVirtualization ? (
          <VirtualizedCompetitorList
            competitors={filteredCompetitors}
            allCompetitors={allCompetitors}
            viewMode="list"
            compareSet={compareSet}
            onToggleCompare={toggleCompare}
          />
        ) : (
          <div className="space-y-2">
            {filteredCompetitors.map((competitor, index) => {
              const competitorId = getCompetitorId(competitor)
              const domId = getCompetitorDomIdFromId(competitorId)
              const rank = competitorRankById.get(competitorId) ?? (index + 1)
              return renderCardWrapper(
                competitorId,
                index,
                '-20px',
                <CompetitorRow
                  competitor={competitor}
                  rank={rank}
                  domId={domId}
                  compareSelected={compareSet.has(competitorId)}
                  onToggleCompare={toggleCompare}
                />,
              )
            })}
          </div>
        ))}

      {filteredCompetitors.length === 0 && (
        <p className="text-center text-sm text-muted-foreground py-6">{t('report.competitors.empty')}</p>
      )}
    </section>
  )
}
