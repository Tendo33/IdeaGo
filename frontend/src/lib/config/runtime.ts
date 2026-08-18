/**
 * Runtime frontend configuration.
 *
 * Public values (Supabase URL / anon key, Turnstile site key, browser Sentry
 * DSN, feature flags) used to be Vite build-time constants. That meant the
 * published Docker image carried whatever the build machine had — and the
 * release workflow passed nothing, so published images shipped a login page
 * that could never work.
 *
 * These values now come from `GET /api/v1/config` at startup, so one image
 * works for any deployment.
 *
 * Resolution order, highest first:
 *   1. runtime config fetched from the backend (non-empty fields only)
 *   2. build-time `VITE_*` values, if the bundle was built with them
 *   3. empty — callers degrade explicitly (fallback Supabase client, disabled
 *      login button) rather than crashing
 *
 * `VITE_API_BASE_URL` deliberately stays build-time: it is needed to locate
 * this very endpoint, so it cannot be delivered by it. Same-origin deployments
 * (the single-container default) leave it empty and need nothing at build time.
 */

export interface RuntimeConfig {
  supabaseUrl: string
  supabaseAnonKey: string
  turnstileSiteKey: string
  sentryDsn: string
  pricingEnabled: boolean
  environment: string
}

function readBuildTimeEnv(): RuntimeConfig {
  const env = import.meta.env
  return {
    supabaseUrl: (env.VITE_SUPABASE_URL ?? '').trim(),
    supabaseAnonKey: (env.VITE_SUPABASE_ANON_KEY ?? '').trim(),
    turnstileSiteKey: (env.VITE_TURNSTILE_SITE_KEY ?? '').trim(),
    sentryDsn: (env.VITE_SENTRY_DSN ?? '').trim(),
    pricingEnabled: false,
    environment: env.MODE ?? 'development',
  }
}

let current: RuntimeConfig | null = null

function asTrimmedString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

/** Runtime values win when present; otherwise keep whatever the build had. */
function mergeOverBuildTime(payload: unknown): RuntimeConfig {
  const base = readBuildTimeEnv()
  if (!payload || typeof payload !== 'object') return base

  const raw = payload as Record<string, unknown>
  return {
    supabaseUrl: asTrimmedString(raw.supabase_url) || base.supabaseUrl,
    supabaseAnonKey: asTrimmedString(raw.supabase_anon_key) || base.supabaseAnonKey,
    turnstileSiteKey: asTrimmedString(raw.turnstile_site_key) || base.turnstileSiteKey,
    sentryDsn: asTrimmedString(raw.sentry_dsn) || base.sentryDsn,
    pricingEnabled:
      typeof raw.pricing_enabled === 'boolean' ? raw.pricing_enabled : base.pricingEnabled,
    environment: asTrimmedString(raw.environment) || base.environment,
  }
}

/**
 * Read the active config. Safe before `loadRuntimeConfig` resolves — falls
 * back to build-time values, which is what unit tests rely on.
 */
export function getRuntimeConfig(): RuntimeConfig {
  return current ?? readBuildTimeEnv()
}

/**
 * Fetch runtime config once at startup.
 *
 * Never rejects: a backend that is down or an older backend without this
 * endpoint degrades to build-time values instead of blocking the whole app.
 */
export async function loadRuntimeConfig(apiBase: string): Promise<RuntimeConfig> {
  try {
    const response = await fetch(`${apiBase}/config`, {
      headers: { Accept: 'application/json' },
    })
    if (response.ok) {
      current = mergeOverBuildTime(await response.json())
      return current
    }
    console.warn(`Runtime config request failed (${response.status}); using build-time values.`)
  } catch (error) {
    console.warn('Runtime config request failed; using build-time values.', error)
  }
  current = readBuildTimeEnv()
  return current
}

/** Test seam: install a known config without touching the network. */
export function setRuntimeConfig(config: Partial<RuntimeConfig>): void {
  current = { ...readBuildTimeEnv(), ...config }
}

/** Test seam: drop back to build-time values. */
export function resetRuntimeConfig(): void {
  current = null
}
