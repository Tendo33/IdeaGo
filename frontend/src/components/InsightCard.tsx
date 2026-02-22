import { motion } from 'framer-motion'
import { Lightbulb } from 'lucide-react'

interface InsightCardProps {
  angle: string
  index: number
}

export function InsightCard({ angle, index }: InsightCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ delay: index * 0.1, duration: 0.4, ease: 'easeOut' }}
      className="rounded-xl border border-cta/20 bg-cta/5 p-4 transition-all duration-200 hover:border-cta/40 hover:bg-cta/8"
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-cta/15 flex items-center justify-center shrink-0 mt-0.5">
          <Lightbulb className="w-4 h-4 text-cta" />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-text-dim mb-1">Opportunity #{index + 1}</p>
          <p className="text-sm text-text leading-relaxed">{angle}</p>
        </div>
      </div>
    </motion.div>
  )
}

interface InsightsSectionProps {
  angles: string[]
}

export function InsightsSection({ angles }: InsightsSectionProps) {
  if (angles.length === 0) return null

  return (
    <section id="section-opportunities">
      <h2 className="text-lg font-semibold font-[family-name:var(--font-heading)] text-text mb-4 flex items-center gap-2">
        <Lightbulb className="w-5 h-5 text-cta" />
        Differentiation Opportunities
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {angles.map((angle, i) => (
          <InsightCard key={i} angle={angle} index={i} />
        ))}
      </div>
    </section>
  )
}
