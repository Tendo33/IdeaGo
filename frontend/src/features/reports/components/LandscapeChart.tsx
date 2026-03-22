import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { getCompetitorDomId } from '../competitor'
import type { Competitor } from '@/lib/types/research'

interface LandscapeChartProps {
  competitors: Competitor[]
}

interface DataPoint {
  name: string
  oneLiner: string
  features: number
  relevance: number
  sources: number
  domId: string
}

const ZONE_COLORS = {
  high: 'var(--primary)',
  medium: 'var(--warning)',
  low: 'var(--color-text-dim)',
}

function getColor(relevance: number): string {
  if (relevance >= 70) return ZONE_COLORS.high
  if (relevance >= 40) return ZONE_COLORS.medium
  return ZONE_COLORS.low
}

function getRadius(sources: number): number {
  if (sources >= 3) return 10
  if (sources >= 2) return 7
  return 5
}

function CustomTooltip({ active, payload, t }: { active?: boolean; payload?: Array<{ payload: DataPoint }>; t: TFunction }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-none bg-popover border-2 border-border p-3 shadow max-w-xs">
      <p className="text-sm font-semibold text-foreground mb-0.5">{d.name}</p>
      <p className="text-xs text-muted-foreground mb-1.5 line-clamp-2">{d.oneLiner}</p>
      <div className="flex gap-3 text-xs text-muted-foreground">
        <span>{t('report.chart.relevance').replace(' %', '')}: <span className="font-medium text-foreground">{d.relevance}%</span></span>
        <span>{t('report.compare.features')}: <span className="font-medium text-foreground">{d.features}</span></span>
        <span>{t('report.compare.sources')}: <span className="font-medium text-foreground">{d.sources}</span></span>
      </div>
    </div>
  )
}

export function LandscapeChart({ competitors }: LandscapeChartProps) {
  const { t } = useTranslation()
  const highlightTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const highlightedElementRef = useRef<HTMLElement | null>(null)

  useEffect(() => () => {
    if (highlightTimerRef.current) {
      clearTimeout(highlightTimerRef.current)
      highlightTimerRef.current = null
    }
    if (highlightedElementRef.current) {
      highlightedElementRef.current.classList.remove('ring-2', 'ring-primary')
      highlightedElementRef.current = null
    }
  }, [])

  if (competitors.length === 0) return null

  const data: DataPoint[] = competitors.map(c => ({
    name: c.name,
    oneLiner: c.one_liner,
    features: c.features.length,
    relevance: Math.round(c.relevance_score * 100),
    sources: c.source_platforms.length,
    domId: getCompetitorDomId(c),
  }))

  const maxFeatures = Math.max(...data.map(d => d.features), 1)

  const handleClick = (d: DataPoint) => {
    const el = document.getElementById(d.domId)
    if (el) {
      if (highlightTimerRef.current) {
        clearTimeout(highlightTimerRef.current)
        highlightTimerRef.current = null
      }
      if (highlightedElementRef.current && highlightedElementRef.current !== el) {
        highlightedElementRef.current.classList.remove('ring-2', 'ring-primary')
      }
      highlightedElementRef.current = el
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('ring-2', 'ring-primary')
      highlightTimerRef.current = setTimeout(() => {
        el.classList.remove('ring-2', 'ring-primary')
        if (highlightedElementRef.current === el) {
          highlightedElementRef.current = null
        }
        highlightTimerRef.current = null
      }, 2000)
    }
  }

  return (
    <div className="rounded-none border-2 border-border bg-card shadow p-5 hover:border-ring/35 transition-colors duration-300">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold font-heading text-foreground">
          {t('report.chart.title')}
        </h3>
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-none bg-primary" /> {t('report.chart.high')}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-none bg-warning" /> {t('report.chart.medium')}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-none bg-text-dim" /> {t('report.chart.low')}</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.65} />
          <XAxis
            dataKey="features"
            type="number"
            name="Features"
            domain={[0, maxFeatures + 1]}
            tick={{ fontSize: 10, fill: 'var(--color-text-dim)' }}
            label={{ value: t('report.chart.featureCount'), position: 'insideBottom', offset: -10, fontSize: 10, fill: 'var(--color-text-dim)' }}
          />
          <YAxis
            dataKey="relevance"
            type="number"
            name="Relevance"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: 'var(--color-text-dim)' }}
            label={{ value: t('report.chart.relevance'), angle: -90, position: 'insideLeft', offset: 10, fontSize: 10, fill: 'var(--color-text-dim)' }}
          />
          <ReferenceLine y={70} stroke="var(--primary)" strokeDasharray="4 4" opacity={0.45} />
          <ReferenceLine y={40} stroke="var(--warning)" strokeDasharray="4 4" opacity={0.45} />
          <Tooltip content={<CustomTooltip t={t} />} cursor={false} />
          <Scatter
            data={data}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            onClick={(entry: any) => handleClick(entry)}
            className="cursor-pointer"
          >
            {data.map((d, i) => (
              <Cell
                key={i}
                fill={getColor(d.relevance)}
                r={getRadius(d.sources)}
                fillOpacity={0.8}
                stroke={getColor(d.relevance)}
                strokeWidth={1}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      <p className="text-[10px] text-muted-foreground text-center mt-2">
        {t('report.chart.clickHint')}
      </p>
    </div>
  )
}
