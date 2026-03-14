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
    <div className="fixed top-16 left-0 right-0 z-40 no-print animate-fade-in">
      <div className="max-w-5xl mx-auto px-4">
        <nav className="flex items-center gap-1 px-2 py-1.5 rounded-xl bg-popover/95 backdrop-blur-2xl border border-border/80 shadow-xl overflow-x-auto">
          {sections.map(s => (
            <button
              key={s.id}
              onClick={() => handleClick(s.id)}
              className={`filter-chip rounded-lg px-3 py-1.5 font-medium whitespace-nowrap ${resolvedActiveId === s.id ? 'filter-chip-active' : ''}`}
            >
              {s.label}
              {s.count !== undefined && (
                <span className="ml-1 text-[10px] opacity-70">({s.count})</span>
              )}
            </button>
          ))}
        </nav>
      </div>
    </div>
  )
}
