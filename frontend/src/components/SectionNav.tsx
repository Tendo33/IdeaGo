import { useEffect, useState } from 'react'

interface NavSection {
  id: string
  label: string
  count?: number
}

interface SectionNavProps {
  sections: NavSection[]
}

export function SectionNav({ sections }: SectionNavProps) {
  const [activeId, setActiveId] = useState<string>(sections[0]?.id ?? '')
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const sectionEls = sections
      .map(s => document.getElementById(s.id))
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
  }, [sections])

  if (!visible) return null

  const handleClick = (id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  return (
    <div className="fixed top-16 left-0 right-0 z-40 no-print animate-fade-in">
      <div className="max-w-5xl mx-auto px-4">
        <nav className="flex items-center gap-1 px-2 py-1.5 rounded-xl bg-bg-card/90 backdrop-blur-md border border-border shadow-lg shadow-black/20 overflow-x-auto">
          {sections.map(s => (
            <button
              key={s.id}
              onClick={() => handleClick(s.id)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg whitespace-nowrap cursor-pointer transition-all duration-200 ${
                activeId === s.id
                  ? 'bg-cta/15 text-cta'
                  : 'text-text-dim hover:text-text-muted hover:bg-secondary/50'
              }`}
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
