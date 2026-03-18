interface RelevanceRingProps {
  score: number
  size?: number
}

export function RelevanceRing({ score, size = 36 }: RelevanceRingProps) {
  const percent = Math.round(score * 100)
  const radius = (size - 6) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (score * circumference)

  const color = percent >= 70
    ? 'stroke-cta'
    : percent >= 40
      ? 'stroke-warning'
      : 'stroke-text-dim'

  const textColor = percent >= 70
    ? 'fill-cta'
    : percent >= 40
      ? 'fill-warning'
      : 'fill-text-dim'

  return (
    <svg width={size} height={size} className="shrink-0" aria-label={`Relevance: ${percent}%`}>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="currentColor"
        className="text-border"
        strokeWidth={3}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        className={color}
        strokeWidth={3}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 600ms ease-out' }}
      />
      <text
        x={size / 2}
        y={size / 2}
        textAnchor="middle"
        dominantBaseline="central"
        className={`${textColor} text-[9px] font-semibold`}
      >
        {percent}%
      </text>
    </svg>
  )
}
