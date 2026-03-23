import { Check, Globe, Minus, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/Badge'
import { getCompetitorId } from '../competitor'
import { PlatformIcon, platformColors } from './PlatformIcons'
import { RelevanceRing } from './RelevanceRing'
import type { Competitor } from '@/lib/types/research'

interface ComparePanelDesktopTableProps {
  competitors: Competitor[]
  allFeatures: string[]
  onRemove: (competitorId: string) => void
}

export function ComparePanelDesktopTable({ competitors, allFeatures, onRemove }: ComparePanelDesktopTableProps) {
  const { t } = useTranslation()

  return (
    <div className="hidden sm:block w-full overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b-2 border-border">
            <th className="sticky left-0 bg-popover z-10 text-left px-5 py-4 text-xs font-medium text-muted-foreground w-36 min-w-36" />
            {competitors.map(competitor => {
              const competitorId = getCompetitorId(competitor)
              return (
                <th key={competitorId} className="px-4 py-3 text-left min-w-44 border-l-2 border-border">
                  <div className="flex items-center justify-between gap-2 min-w-0">
                    <span className="text-sm font-semibold text-foreground truncate min-w-0" title={competitor.name}>
                      {competitor.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => onRemove(competitorId)}
                      className="p-2 min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-none text-muted-foreground hover:text-danger hover:bg-muted/50 transition-colors cursor-pointer shrink-0 focus-visible:ring-2 focus-visible:ring-primary"
                      aria-label={t('report.accessibility.removeCompetitor', { name: competitor.name })}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          <tr className="border-b-2 border-border">
            <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium">
              {t('report.compare.relevance')}
            </td>
            {competitors.map(competitor => (
              <td key={`${getCompetitorId(competitor)}-relevance`} className="px-4 py-3 border-l-2 border-border">
                <RelevanceRing score={competitor.relevance_score} size={32} />
              </td>
            ))}
          </tr>

          <tr className="border-b-2 border-border/30">
            <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium">
              {t('report.compare.description')}
            </td>
            {competitors.map(competitor => (
              <td
                key={`${getCompetitorId(competitor)}-description`}
                className="px-4 py-3 text-xs text-foreground leading-relaxed border-l-2 border-border break-words min-w-[200px] whitespace-normal"
              >
                {competitor.one_liner}
              </td>
            ))}
          </tr>

          <tr className="border-b-2 border-border/30">
            <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium">
              {t('report.compare.pricing')}
            </td>
            {competitors.map(competitor => (
              <td key={`${getCompetitorId(competitor)}-pricing`} className="px-4 py-3 text-xs text-foreground font-medium border-l-2 border-border">
                {competitor.pricing ?? '-'}
              </td>
            ))}
          </tr>

          {allFeatures.length > 0 && (
            <tr className="border-b-2 border-border">
              <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-foreground uppercase tracking-wider bg-muted/65">
                {t('report.compare.features')}
              </td>
            </tr>
          )}
          {allFeatures.map(feature => (
            <tr key={feature} className="border-b border-2 border-border/30">
              <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground break-words max-w-[150px] whitespace-normal">{feature}</td>
              {competitors.map(competitor => (
                <td key={`${getCompetitorId(competitor)}-${feature}`} className="px-4 py-2 text-center border-l-2 border-border">
                  {competitor.features.includes(feature) ? (
                    <Check className="w-4 h-4 text-cta inline-block" />
                  ) : (
                    <Minus className="w-4 h-4 text-muted-foreground/40 inline-block" />
                  )}
                </td>
              ))}
            </tr>
          ))}

          <tr className="border-b-2 border-border">
            <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-foreground uppercase tracking-wider bg-muted/65">
              {t('report.compare.strengths')}
            </td>
          </tr>
          <tr className="border-b-2 border-border/30">
            <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium" />
            {competitors.map(competitor => (
              <td key={`${getCompetitorId(competitor)}-strengths`} className="px-4 py-4 align-top border-l-2 border-border min-w-[200px] break-words whitespace-normal">
                <ul className="space-y-2">
                  {competitor.strengths.map((strength, index) => (
                    <li key={index} className="text-xs text-foreground flex items-start gap-1.5 leading-snug">
                      <span className="text-success shrink-0">&bull;</span> <span>{strength}</span>
                    </li>
                  ))}
                </ul>
              </td>
            ))}
          </tr>

          <tr className="border-b-2 border-border">
            <td colSpan={competitors.length + 1} className="px-5 py-3 text-xs font-semibold text-foreground uppercase tracking-wider bg-muted/65">
              {t('report.compare.weaknesses')}
            </td>
          </tr>
          <tr className="border-b-2 border-border/30">
            <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium" />
            {competitors.map(competitor => (
              <td key={`${getCompetitorId(competitor)}-weaknesses`} className="px-4 py-4 align-top border-l-2 border-border min-w-[200px] break-words whitespace-normal">
                <ul className="space-y-2">
                  {competitor.weaknesses.map((weakness, index) => (
                    <li key={index} className="text-xs text-foreground flex items-start gap-1.5 leading-snug">
                      <span className="text-danger shrink-0">&bull;</span> <span>{weakness}</span>
                    </li>
                  ))}
                </ul>
              </td>
            ))}
          </tr>

          <tr>
            <td className="sticky left-0 bg-popover z-10 px-5 py-3 text-xs text-muted-foreground font-medium">
              {t('report.compare.sources')}
            </td>
            {competitors.map(competitor => (
              <td key={`${getCompetitorId(competitor)}-sources`} className="px-4 py-3 border-l-2 border-border">
                <div className="flex gap-2 flex-wrap shrink-0 max-w-[150px]">
                  {competitor.source_platforms.map(platform => {
                    const Icon = PlatformIcon[platform] || Globe
                    return (
                      <Badge key={platform} variant="default" className={`text-[10px] pl-1 pr-1.5 py-0.5 whitespace-nowrap ${platformColors[platform] || ''}`}>
                        <Icon className="w-3 h-3" />
                        {platform}
                      </Badge>
                    )
                  })}
                </div>
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  )
}
