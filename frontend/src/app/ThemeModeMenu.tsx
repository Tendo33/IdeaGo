import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, Monitor, Moon, Sun } from 'lucide-react'

export type ThemeMode = 'system' | 'light' | 'dark'

const THEME_OPTIONS: Array<{
  mode: ThemeMode
  labelKey: string
  shortLabelKey: string
  Icon: typeof Monitor
}> = [
  { mode: 'system', labelKey: 'theme.system', shortLabelKey: 'theme.systemShort', Icon: Monitor },
  { mode: 'dark', labelKey: 'theme.dark', shortLabelKey: 'theme.darkShort', Icon: Moon },
  { mode: 'light', labelKey: 'theme.light', shortLabelKey: 'theme.lightShort', Icon: Sun },
]

export function ThemeModeMenu({
  themeMode,
  onSelectThemeMode,
}: {
  themeMode: ThemeMode
  onSelectThemeMode: (mode: ThemeMode) => void
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([])
  const activeTheme = THEME_OPTIONS.find(option => option.mode === themeMode) ?? THEME_OPTIONS[0]
  const ActiveIcon = activeTheme.Icon
  const selectedIndex = Math.max(0, THEME_OPTIONS.findIndex(option => option.mode === themeMode))

  const focusOption = (index: number) => {
    const next = (index + THEME_OPTIONS.length) % THEME_OPTIONS.length
    setActiveIndex(next)
    optionRefs.current[next]?.focus()
  }

  useEffect(() => {
    if (!open) return

    const onPointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    requestAnimationFrame(() => {
      optionRefs.current[activeIndex]?.focus()
    })
  }, [activeIndex, open])

  const openFromTrigger = (index: number) => {
    const normalizedIndex = (index + THEME_OPTIONS.length) % THEME_OPTIONS.length
    setActiveIndex(normalizedIndex)
    setOpen(true)
  }

  const onTriggerClick = () => {
    if (!open) {
      setActiveIndex(selectedIndex)
    }
    setOpen(previous => !previous)
  }

  const onTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      openFromTrigger(selectedIndex)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      openFromTrigger(THEME_OPTIONS.length - 1)
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openFromTrigger(selectedIndex)
    }
  }

  const onMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusOption(activeIndex + 1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusOption(activeIndex - 1)
      return
    }
    if (event.key === 'Home') {
      event.preventDefault()
      focusOption(0)
      return
    }
    if (event.key === 'End') {
      event.preventDefault()
      focusOption(THEME_OPTIONS.length - 1)
      return
    }
    if (event.key === 'Escape') {
      event.preventDefault()
      setOpen(false)
      triggerRef.current?.focus()
      return
    }
    if (event.key === 'Tab') {
      setOpen(false)
    }
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={onTriggerClick}
        onKeyDown={onTriggerKeyDown}
        className="topbar-action focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        aria-label={t('theme.toggle')}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <ActiveIcon className="h-5 w-5" aria-hidden="true" />
        <span className="hidden sm:inline">{t(activeTheme.shortLabelKey)}</span>
      </button>
      {open && (
        <div
          role="menu"
          aria-label={t('theme.options')}
          onKeyDown={onMenuKeyDown}
          className="absolute right-0 top-full mt-2 w-48 border-2 border-border bg-background p-2 shadow z-50"
        >
          {THEME_OPTIONS.map(option => {
            const OptionIcon = option.Icon
            const selected = option.mode === themeMode
            const index = THEME_OPTIONS.findIndex(themeOption => themeOption.mode === option.mode)
            return (
              <button
                key={option.mode}
                ref={node => {
                  optionRefs.current[index] = node
                }}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
                tabIndex={activeIndex === index ? 0 : -1}
                onClick={() => {
                  onSelectThemeMode(option.mode)
                  setOpen(false)
                }}
                className={`w-full inline-flex items-center justify-between px-3 py-2 text-sm font-bold uppercase tracking-wider transition-all cursor-pointer border-2 border-transparent ${
                  selected
                    ? 'bg-primary text-primary-foreground border-border shadow-sm'
                    : 'text-muted-foreground hover:bg-muted hover:border-border hover:shadow-sm hover:text-foreground'
                }`}
              >
                <span className="inline-flex items-center gap-3">
                  <OptionIcon className="h-4 w-4" aria-hidden="true" />
                  {t(option.labelKey)}
                </span>
                {selected && <Check className="h-4 w-4" aria-hidden="true" />}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
