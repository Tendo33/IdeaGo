import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Share2, Download, Link2, Check, Printer, ChevronDown } from 'lucide-react'
import type { ResearchReport } from '../types/research'
import { getExportUrl } from '../api/client'

interface ReportHeaderProps {
  report: ResearchReport
}

function Dropdown({ trigger, children }: { trigger: React.ReactNode; children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className="inline-flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg bg-secondary text-text font-medium cursor-pointer transition-colors duration-200 hover:bg-bg-card-hover focus:outline-none focus:ring-2 focus:ring-cta/30"
      >
        {trigger}
        <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-150 ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-48 rounded-lg border border-border bg-bg-card shadow-xl shadow-black/30 py-1 z-50">
          {children}
        </div>
      )}
    </div>
  )
}

function DropdownItem({ icon: Icon, label, onClick, href }: { icon: typeof Download; label: string; onClick?: () => void; href?: string }) {
  const cls = "flex items-center gap-2 w-full px-3 py-2 text-sm text-text-muted hover:bg-bg-card-hover hover:text-text transition-colors cursor-pointer"

  if (href) {
    return (
      <a href={href} download className={cls}>
        <Icon className="w-4 h-4" />
        {label}
      </a>
    )
  }

  return (
    <button onClick={onClick} className={cls}>
      <Icon className="w-4 h-4" />
      {label}
    </button>
  )
}

export function ReportHeader({ report }: ReportHeaderProps) {
  const [copied, setCopied] = useState(false)

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="flex flex-col gap-3 mb-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-cta transition-colors duration-200 mb-3 cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4" />
            New search
          </Link>
          <h1 className="text-2xl font-bold font-[family-name:var(--font-heading)] text-text mb-1">
            {report.query}
          </h1>
          <p className="text-xs text-text-dim">
            {report.intent.app_type} &middot; {report.intent.keywords_en.join(', ')} &middot; {new Date(report.created_at).toLocaleString()}
          </p>
        </div>

        <div className="flex items-center gap-2 shrink-0 no-print">
          <Dropdown trigger={<><Share2 className="w-4 h-4" /><span className="hidden sm:inline"> Share</span></>}>
            <DropdownItem
              icon={copied ? Check : Link2}
              label={copied ? 'Copied!' : 'Copy Link'}
              onClick={handleCopyLink}
            />
          </Dropdown>
          <Dropdown trigger={<><Download className="w-4 h-4" /><span className="hidden sm:inline"> Export</span></>}>
            <DropdownItem
              icon={Download}
              label="Markdown"
              href={getExportUrl(report.id)}
            />
            <DropdownItem
              icon={Printer}
              label="Print / PDF"
              onClick={() => window.print()}
            />
          </Dropdown>
        </div>
      </div>
    </div>
  )
}
