import { useState, useRef, useEffect, useId } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Share2, Download, Link2, Check, Printer, ChevronDown } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { ResearchReport } from '@/lib/types/research'
import { getExportUrl } from '@/lib/api/client'

interface ReportHeaderProps {
  report: ResearchReport
}

function Dropdown({ trigger, children }: { trigger: React.ReactNode; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const ref = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return

    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }

    document.addEventListener('mousedown', handleClick)
    document.addEventListener('keydown', handleKeyDown)

    const firstMenuItem = ref.current?.querySelector<HTMLElement>('[role="menuitem"]')
    firstMenuItem?.focus()

    return () => {
      document.removeEventListener('mousedown', handleClick)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        ref={triggerRef}
        onClick={() => setOpen(o => !o)}
        className="topbar-action text-sm font-medium focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
      >
        {trigger}
        <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-150 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 top-full mt-1.5 w-48 rounded-none border border-2 border-border bg-popover/95 backdrop-blur-2xl shadow-[4px_4px_0px_0px_var(--border)] py-1 z-50 overflow-hidden outline-none"
          onClick={event => {
            if ((event.target as HTMLElement).closest('[role="menuitem"]')) {
              setOpen(false)
            }
          }}
          tabIndex={-1}
        >
          {children}
        </div>
      )}
    </div>
  )
}

function DropdownItem({ icon: Icon, label, onClick, href }: { icon: typeof Download; label: string; onClick?: () => void; href?: string }) {
  const cls = "flex items-center gap-2 w-full rounded-none px-3 py-2 text-sm text-muted-foreground hover:bg-muted/65 hover:text-foreground transition-colors cursor-pointer"

  if (href) {
    return (
      <a href={href} download className={cls} role="menuitem">
        <Icon className="w-4 h-4" />
        {label}
      </a>
    )
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={cls}
      role="menuitem"
      tabIndex={0}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  )
}

export function ReportHeader({ report }: ReportHeaderProps) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState<string | null>(null)
  const feedbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => () => {
    if (feedbackTimerRef.current) {
      clearTimeout(feedbackTimerRef.current)
    }
  }, [])

  const handleCopyLink = async () => {
    if (feedbackTimerRef.current) {
      clearTimeout(feedbackTimerRef.current)
      feedbackTimerRef.current = null
    }
    setCopyError(null)

    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('Clipboard API unavailable')
      }
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      feedbackTimerRef.current = setTimeout(() => {
        setCopied(false)
        feedbackTimerRef.current = null
      }, 2000)
    } catch {
      setCopied(false)
      setCopyError(t('report.header.copyFailed'))
      feedbackTimerRef.current = setTimeout(() => {
        setCopyError(null)
        feedbackTimerRef.current = null
      }, 3000)
    }
  }

  return (
    <div className="flex flex-col gap-3 mb-6">
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div className="min-w-0 flex-1 w-full">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-cta transition-colors duration-200 mb-3 cursor-pointer focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none rounded-none px-1"
          >
            <ArrowLeft className="w-4 h-4" />
            {t('report.header.newSearch')}
          </Link>
          <h1 className="text-2xl font-bold font-heading text-foreground mb-1 break-words">
            {report.query}
          </h1>
          <p className="text-xs text-muted-foreground break-words leading-relaxed">
            {report.intent.app_type} &middot; {report.intent.keywords_en.join(', ')} &middot; <span className="whitespace-nowrap">{new Date(report.created_at).toLocaleString()}</span>
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 no-print w-full md:w-auto mt-2 md:mt-0">
          <Dropdown trigger={<div className="flex items-center gap-2"><Share2 className="w-4 h-4" /><span className="hidden sm:inline"> {t('report.header.share')}</span></div>}>
            <DropdownItem
              icon={copied ? Check : Link2}
              label={copied ? t('report.header.copied') : t('report.header.copyLink')}
              onClick={handleCopyLink}
            />
          </Dropdown>
          <Dropdown trigger={<div className="flex items-center gap-2"><Download className="w-4 h-4" /><span className="hidden sm:inline"> {t('report.header.export')}</span></div>}>
            <DropdownItem
              icon={Download}
              label={t('report.header.markdown')}
              href={getExportUrl(report.id)}
            />
            <DropdownItem
              icon={Printer}
              label={t('report.header.print')}
              onClick={() => window.print()}
            />
          </Dropdown>
        </div>
      </div>
      {copyError && (
        <p className="text-xs text-danger">{copyError}</p>
      )}
    </div>
  )
}
