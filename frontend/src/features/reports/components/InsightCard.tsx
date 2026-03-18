import { motion, useReducedMotion } from 'framer-motion'
import { Lightbulb } from 'lucide-react'
import { useTranslation } from 'react-i18next'

interface InsightCardProps {
  angle: string
  index: number
}

export function InsightCard({ angle, index }: InsightCardProps) {
  const { t } = useTranslation()
  const reduceMotion = Boolean(useReducedMotion())

  const content = (
    <div className="flex items-start gap-4">
      <div className="w-10 h-10 rounded-none bg-cta/15 flex items-center justify-center shrink-0 mt-0.5">
        <Lightbulb className="w-5 h-5 text-cta" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-bold text-muted-foreground mb-2 break-words">{t('report.insight.opportunity')}{index + 1}</p>
        <p className="text-base text-foreground leading-relaxed break-words">{angle}</p>
      </div>
    </div>
  )

  if (reduceMotion) {
    return (
      <div className="rounded-none border border-cta/20 bg-cta/5 p-6 transition-all duration-200 hover:border-cta/40 hover:bg-cta/8">
        {content}
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ delay: index * 0.1, duration: 0.4, ease: 'easeOut' }}
      className="rounded-none border border-cta/20 bg-cta/5 p-6 transition-all duration-200 hover:border-cta/40 hover:bg-cta/8"
    >
      {content}
    </motion.div>
  )
}

interface InsightsSectionProps {
  angles: string[]
}

export function InsightsSection({ angles }: InsightsSectionProps) {
  const { t } = useTranslation()
  if (angles.length === 0) return null

  return (
    <section id="section-opportunities">
      <h2 className="text-xl font-bold font-heading text-foreground mb-5 flex items-center gap-2">
        <Lightbulb className="w-6 h-6 text-cta" />
        {t('report.insight.title')}
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
        {angles.map((angle, i) => (
          <InsightCard key={i} angle={angle} index={i} />
        ))}
      </div>
    </section>
  )
}
