import { useEffect, useRef } from 'react'
import type { TFunction } from 'i18next'
import {
  getTurnstileMessage,
  TURNSTILE_SCRIPT_ID,
  TURNSTILE_SCRIPT_SRC,
} from './turnstileUtils'

export type TurnstileStatus = 'verifying' | 'success' | 'expired' | 'error' | 'unsupported'
export type TurnstileTheme = 'light' | 'dark'

type TurnstileRenderOptions = {
  sitekey: string
  callback?: (token: string) => void
  'expired-callback'?: () => void
  'error-callback'?: () => void
  appearance?: 'always' | 'execute' | 'interaction-only'
  execution?: 'render' | 'execute'
  retry?: 'auto' | 'never'
  'refresh-expired'?: 'auto' | 'manual' | 'never'
  theme?: 'light' | 'dark' | 'auto'
}

type TurnstileApi = {
  render: (container: HTMLElement, options: TurnstileRenderOptions) => string
  reset: (widgetId?: string) => void
  remove?: (widgetId?: string) => void
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
    __ideagoTurnstileOnLoad?: () => void
  }
}

interface TurnstilePanelProps {
  siteKey: string
  status: TurnstileStatus
  theme: TurnstileTheme
  onTokenChange: (token: string | null) => void
  onStatusChange: (status: TurnstileStatus) => void
  t: TFunction
}

export function TurnstilePanel({
  siteKey,
  status,
  theme,
  onTokenChange,
  onStatusChange,
  t,
}: TurnstilePanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const widgetIdRef = useRef<string | null>(null)

  useEffect(() => {
    if (!siteKey) {
      onTokenChange(null)
      onStatusChange('unsupported')
      return
    }

    let disposed = false

    const renderWidget = () => {
      if (disposed || !containerRef.current || !window.turnstile || widgetIdRef.current) {
        return
      }

      onStatusChange('verifying')
      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: siteKey,
        appearance: 'always',
        execution: 'render',
        retry: 'auto',
        'refresh-expired': 'auto',
        theme,
        callback: token => {
          if (disposed) {
            return
          }
          onTokenChange(token)
          onStatusChange('success')
        },
        'expired-callback': () => {
          if (disposed) {
            return
          }
          onTokenChange(null)
          onStatusChange('expired')
          window.turnstile?.reset(widgetIdRef.current ?? undefined)
        },
        'error-callback': () => {
          if (disposed) {
            return
          }
          onTokenChange(null)
          onStatusChange('error')
          window.turnstile?.reset(widgetIdRef.current ?? undefined)
        },
      })
    }

    if (window.turnstile) {
      renderWidget()
    } else {
      window.__ideagoTurnstileOnLoad = renderWidget
      let script = document.getElementById(TURNSTILE_SCRIPT_ID) as HTMLScriptElement | null

      if (!script) {
        script = document.createElement('script')
        script.id = TURNSTILE_SCRIPT_ID
        script.src = TURNSTILE_SCRIPT_SRC
        script.async = true
        script.defer = true
        script.onload = () => window.__ideagoTurnstileOnLoad?.()
        script.onerror = () => {
          if (disposed) {
            return
          }
          onTokenChange(null)
          onStatusChange('error')
        }
        document.head.appendChild(script)
      } else {
        script.addEventListener('load', window.__ideagoTurnstileOnLoad)
      }
    }

    return () => {
      disposed = true
      if (widgetIdRef.current) {
        window.turnstile?.remove?.(widgetIdRef.current)
        widgetIdRef.current = null
      }
    }
  }, [onStatusChange, onTokenChange, siteKey, theme])

  return (
    <div className="space-y-3">
      <div className="border-2 border-border bg-background/80 p-4 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-widest text-muted-foreground">
              {t('auth.humanVerification', 'Human verification')}
            </p>
            <p className="mt-2 text-sm font-medium text-foreground">
              {getTurnstileMessage(t, siteKey ? status : 'unsupported')}
            </p>
          </div>
        </div>
        <div ref={containerRef} className="mt-4 min-h-[65px]" aria-live="polite" />
      </div>
    </div>
  )
}
