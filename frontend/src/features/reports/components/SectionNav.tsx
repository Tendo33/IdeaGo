import { useTranslation } from 'react-i18next'
import { useEffect, useMemo, useState } from 'react'

interface NavSection {
  id: string
  label: string
  count?: number
}

interface SectionNavProps {
  sections: NavSection[]
  sectionIdsKey?: string
}

export function SectionNav({ sections, sectionIdsKey }: SectionNavProps) {
  const { t } = useTranslation()
  const [activeId, setActiveId] = useState<string>(sections[0]?.id ?? '')
  const [visible, setVisible] = useState(false)
  const stableSectionIdsKey = sectionIdsKey ?? sections.map(section => section.id).join('|')
  const sectionIds = useMemo(
    () => stableSectionIdsKey.split('|').filter(Boolean),
    [stableSectionIdsKey],
  )
  const resolvedActiveId = sectionIds.includes(activeId) ? activeId : (sectionIds[0] ?? '')

  useEffect(() => {
    const sectionEls = sectionIds
      .map(id => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null)

    if (sectionEls.length === 0) return

    const observer = new IntersectionObserver(
      entries => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id)
          }
        }
      },
      { rootMargin: '-80px 0px -60% 0px', threshold: 0.1 }
    )

    for (const el of sectionEls) observer.observe(el)

    const handleScroll = () => {
      setVisible(window.scrollY > 300)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()

    return () => {
      observer.disconnect()
      window.removeEventListener('scroll', handleScroll)
    }
  }, [sectionIds])

  if (!visible) return null

  const handleClick = (id: string) => {
    const el = document.getElementById(id)
    if (el) {
      const prefersReducedMotion =
        typeof window !== 'undefined' &&
        typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches
      el.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' })
    }
  }

  return (
    <div className="fixed inset-x-0 top-[4.75rem] z-40 no-print animate-fade-in px-3 sm:px-4">
      <div className="mx-auto flex max-w-5xl justify-center">
        <nav
          aria-label={t('report.sections.navigation')}
          className="flex w-fit max-w-full items-center gap-1.5 overflow-x-auto rounded-[1.75rem] border border-border/60 bg-background/88 px-2.5 py-2 shadow-[0_12px_28px_-18px_color-mix(in_oklch,var(--foreground)_26%,transparent)] backdrop-blur-xl supports-[backdrop-filter]:bg-background/78"
        >
          {sections.map(s => (
            <button
              key={s.id}
              onClick={() => handleClick(s.id)}
              className={[
                'group inline-flex min-h-[44px] shrink-0 items-center gap-1.5 rounded-[1.15rem] border px-3.5 py-2 text-xs font-semibold tracking-tight transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 sm:text-sm',
                resolvedActiveId === s.id
                  ? 'border-primary/20 bg-primary text-primary-foreground shadow-[0_10px_20px_-16px_color-mix(in_oklch,var(--primary)_65%,transparent)]'
                  : 'border-transparent bg-transparent text-muted-foreground hover:border-border/70 hover:bg-muted/70 hover:text-foreground',
              ].join(' ')}
              aria-current={resolvedActiveId === s.id ? 'location' : undefined}
            >
              <span className="whitespace-nowrap">{s.label}</span>
              {s.count !== undefined && (
                <span
                  className={[
                    'inline-flex min-w-[1.5rem] items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-bold leading-none',
                    resolvedActiveId === s.id
                      ? 'bg-primary-foreground/16 text-primary-foreground'
                      : 'bg-muted text-muted-foreground group-hover:bg-background/80 group-hover:text-foreground',
                  ].join(' ')}
                >
                  {s.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>
    </div>
  )
}
