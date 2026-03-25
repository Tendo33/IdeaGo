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
  const containerRef = useRef<HTMLDivElement>(null)
  const activeTheme = THEME_OPTIONS.find(option => option.mode === themeMode) ?? THEME_OPTIONS[0]
  const ActiveIcon = activeTheme.Icon

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

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen(previous => !previous)}
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
          className="absolute right-0 top-full mt-2 w-48 border-2 border-border bg-background p-2 shadow z-50"
        >
          {THEME_OPTIONS.map(option => {
            const OptionIcon = option.Icon
            const selected = option.mode === themeMode
            return (
              <button
                key={option.mode}
                type="button"
                role="menuitemradio"
                aria-checked={selected}
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
