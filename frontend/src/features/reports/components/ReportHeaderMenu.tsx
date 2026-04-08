import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { ChevronDown, type LucideIcon } from 'lucide-react'
import { buttonVariants } from '@/components/ui/Button'

interface DropdownProps {
  trigger: ReactNode
  children: ReactNode
}

export function Dropdown({ trigger, children }: DropdownProps) {
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const initialFocusRef = useRef<'first' | 'last'>('first')

  const getMenuItems = () => {
    const menu = menuRef.current
    if (!menu) return []
    return Array.from(
      menu.querySelectorAll<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])'),
    )
  }

  const focusMenuItem = (index: number) => {
    const items = getMenuItems()
    if (items.length === 0) return
    const next = (index + items.length) % items.length
    items[next]?.focus()
  }

  useEffect(() => {
    if (!open) return

    function handleClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false)
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKeyDown)

    const menuItems = getMenuItems()
    if (menuItems.length > 0) {
      const initialIndex = initialFocusRef.current === 'last' ? menuItems.length - 1 : 0
      menuItems[initialIndex]?.focus()
    }

    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const onTriggerKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      initialFocusRef.current = 'first'
      setOpen(true)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      initialFocusRef.current = 'last'
      setOpen(true)
      return
    }
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      initialFocusRef.current = 'first'
      setOpen(true)
    }
  }

  const onMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const menuItems = getMenuItems()
    if (menuItems.length === 0) return
    const focusedIndex = menuItems.findIndex((item) => item === document.activeElement)
    const currentIndex = focusedIndex >= 0 ? focusedIndex : 0

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusMenuItem(currentIndex + 1)
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusMenuItem(currentIndex - 1)
      return
    }
    if (event.key === 'Home') {
      event.preventDefault()
      focusMenuItem(0)
      return
    }
    if (event.key === 'End') {
      event.preventDefault()
      focusMenuItem(menuItems.length - 1)
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
    <div className="relative" ref={ref}>
      <button
        ref={triggerRef}
        onClick={() => setOpen((current) => !current)}
        onKeyDown={onTriggerKeyDown}
        className={buttonVariants({
          variant: 'secondary',
          size: 'sm',
          className: 'justify-between gap-1 px-3',
        })}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
      >
        <span className="inline-flex min-w-0 items-center gap-1.5">{trigger}</span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200 ease-out ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        />
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          ref={menuRef}
          className="absolute right-0 top-[calc(100%+4px)] z-50 mt-0 w-48 rounded-none border-2 border-border bg-popover/95 py-1.5 shadow backdrop-blur-2xl outline-none animate-fade-in"
          onKeyDown={onMenuKeyDown}
          onClick={(event) => {
            if ((event.target as HTMLElement).closest('[role="menuitem"]')) {
              setOpen(false)
            }
          }}
          tabIndex={-1}
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}

interface DropdownItemProps {
  icon: LucideIcon
  label: string
  onClick?: () => void
  href?: string
}

export function DropdownItem({ icon: Icon, label, onClick, href }: DropdownItemProps) {
  const cls = buttonVariants({
    variant: 'ghost',
    size: 'sm',
    className: 'w-full justify-start gap-2.5 px-3.5 text-left normal-case tracking-normal',
  })

  if (href) {
    return (
      <a href={href} download className={cls} role="menuitem">
        <Icon className="h-4 w-4 shrink-0" />
        {label}
      </a>
    )
  }

  return (
    <button type="button" onClick={onClick} className={cls} role="menuitem" tabIndex={0}>
      <Icon className="h-4 w-4 shrink-0" />
      {label}
    </button>
  )
}
