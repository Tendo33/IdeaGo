import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Cell } from 'recharts'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import type { Competitor } from '../types/research'

interface LandscapeChartProps {
  competitors: Competitor[]
}

interface DataPoint {
  name: string
  oneLiner: string
  features: number
  relevance: number
  sources: number
  index: number
}

const ZONE_COLORS = {
  high: '#22C55E',
  medium: '#F59E0B',
  low: '#64748B',
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
    <div className="rounded-lg bg-bg-card border border-border p-3 shadow-xl shadow-black/30 max-w-xs">
      <p className="text-sm font-semibold text-text mb-0.5">{d.name}</p>
      <p className="text-xs text-text-muted mb-1.5 line-clamp-2">{d.oneLiner}</p>
      <div className="flex gap-3 text-xs text-text-dim">
        <span>{t('report.chart.relevance').replace(' %', '')}: <span className="font-medium text-text">{d.relevance}%</span></span>
        <span>{t('report.compare.features')}: <span className="font-medium text-text">{d.features}</span></span>
        <span>{t('report.compare.sources')}: <span className="font-medium text-text">{d.sources}</span></span>
      </div>
    </div>
  )
}

export function LandscapeChart({ competitors }: LandscapeChartProps) {
  const { t } = useTranslation()
  if (competitors.length === 0) return null

  const data: DataPoint[] = competitors.map((c, i) => ({
    name: c.name,
    oneLiner: c.one_liner,
    features: c.features.length,
    relevance: Math.round(c.relevance_score * 100),
    sources: c.source_platforms.length,
    index: i,
  }))

  const maxFeatures = Math.max(...data.map(d => d.features), 1)

  const handleClick = (d: DataPoint) => {
    const el = document.getElementById(`competitor-${d.index + 1}`)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('ring-2', 'ring-cta/50')
      setTimeout(() => el.classList.remove('ring-2', 'ring-cta/50'), 2000)
    }
  }

  return (
    <div className="rounded-xl border border-border bg-bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold font-heading text-text">
          {t('report.chart.title')}
        </h3>
        <div className="flex items-center gap-3 text-[10px] text-text-dim">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-cta" /> {t('report.chart.high')}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-warning" /> {t('report.chart.medium')}</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-text-dim" /> {t('report.chart.low')}</span>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={280}>
        <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.5} />
          <XAxis
            dataKey="features"
            type="number"
            name="Features"
            domain={[0, maxFeatures + 1]}
            tick={{ fontSize: 10, fill: '#64748B' }}
            label={{ value: t('report.chart.featureCount'), position: 'insideBottom', offset: -10, fontSize: 10, fill: '#64748B' }}
          />
          <YAxis
            dataKey="relevance"
            type="number"
            name="Relevance"
            domain={[0, 100]}
            tick={{ fontSize: 10, fill: '#64748B' }}
            label={{ value: t('report.chart.relevance'), angle: -90, position: 'insideLeft', offset: 10, fontSize: 10, fill: '#64748B' }}
          />
          <ReferenceLine y={70} stroke="#22C55E" strokeDasharray="4 4" opacity={0.4} />
          <ReferenceLine y={40} stroke="#F59E0B" strokeDasharray="4 4" opacity={0.4} />
          <Tooltip content={<CustomTooltip t={t} />} cursor={false} />
          <Scatter
            data={data}
            onClick={(entry: DataPoint) => handleClick(entry)}
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

      <p className="text-[10px] text-text-dim text-center mt-2">
        {t('report.chart.clickHint')}
      </p>
    </div>
  )
}
