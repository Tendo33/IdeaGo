import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import * as Sentry from '@sentry/react'
import '../styles/globals.css'
import { API_BASE } from '@/lib/api/core'
import { loadRuntimeConfig, type RuntimeConfig } from '@/lib/config/runtime'

/**
 * Bootstrap order matters here.
 *
 * Public config (Supabase URL / anon key, Turnstile site key, Sentry DSN) is
 * fetched from the backend rather than baked into the bundle, so one image
 * works for any deployment. Modules that read that config do so while they are
 * being evaluated — `lib/supabase/client.ts` calls `createClient` at module
 * scope — which means the whole app module graph must be imported *after* the
 * config resolves. Hence the dynamic imports below: a static
 * `import App from './App'` would evaluate the Supabase client before the
 * fetch completes and permanently pin it to the empty fallback.
 *
 * `loadRuntimeConfig` never rejects; it falls back to build-time `VITE_*`
 * values so local `pnpm dev` and older deployments keep working.
 */
function initSentry(config: RuntimeConfig): void {
  if (!config.sentryDsn) return
  Sentry.init({
    dsn: config.sentryDsn,
    environment: config.environment,
    tracesSampleRate: 0.1,
    sendDefaultPii: false,
  })
}

async function bootstrap(): Promise<void> {
  const config = await loadRuntimeConfig(API_BASE)
  initSentry(config)

  await import('@/lib/i18n/i18n')
  const { default: App } = await import('./App')

  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void bootstrap()
