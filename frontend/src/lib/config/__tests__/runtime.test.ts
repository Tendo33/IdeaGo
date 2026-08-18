import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getRuntimeConfig,
  loadRuntimeConfig,
  resetRuntimeConfig,
  setRuntimeConfig,
} from '../runtime'

const API_BASE = '/api/v1'

/** `Response.json()` returns a promise; a bare object would not typecheck. */
function mockFetchOnce(init: { ok: boolean; status?: number; body?: unknown }) {
  const response = {
    ok: init.ok,
    status: init.status ?? (init.ok ? 200 : 500),
    json: () => Promise.resolve(init.body),
  } as Response
  const fetchMock = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  resetRuntimeConfig()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('runtime config', () => {
  it('falls back to build-time values before load resolves', () => {
    // Nothing loaded yet: callers must still get a usable object, not a throw.
    expect(getRuntimeConfig()).toMatchObject({
      supabaseUrl: expect.any(String),
      supabaseAnonKey: expect.any(String),
      turnstileSiteKey: expect.any(String),
      pricingEnabled: false,
    })
  })

  it('applies values fetched from the backend', async () => {
    mockFetchOnce({
      ok: true,
      body: {
        supabase_url: 'https://runtime.supabase.co',
        supabase_anon_key: 'runtime-anon',
        turnstile_site_key: 'runtime-turnstile',
        sentry_dsn: 'https://runtime@sentry.io/1',
        pricing_enabled: true,
        environment: 'production',
      },
    })

    const config = await loadRuntimeConfig(API_BASE)

    expect(config).toEqual({
      supabaseUrl: 'https://runtime.supabase.co',
      supabaseAnonKey: 'runtime-anon',
      turnstileSiteKey: 'runtime-turnstile',
      sentryDsn: 'https://runtime@sentry.io/1',
      pricingEnabled: true,
      environment: 'production',
    })
    expect(getRuntimeConfig()).toEqual(config)
  })

  it('requests the config endpoint under the API base', async () => {
    const fetchMock = mockFetchOnce({ ok: true, body: {} })
    await loadRuntimeConfig(API_BASE)
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/config', {
      headers: { Accept: 'application/json' },
    })
  })

  it('does not reject when the backend is unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    vi.spyOn(console, 'warn').mockImplementation(() => {})

    await expect(loadRuntimeConfig(API_BASE)).resolves.toMatchObject({
      pricingEnabled: false,
    })
  })

  it('does not reject when the endpoint is missing (older backend)', async () => {
    mockFetchOnce({ ok: false, status: 404 })
    vi.spyOn(console, 'warn').mockImplementation(() => {})

    await expect(loadRuntimeConfig(API_BASE)).resolves.toMatchObject({
      pricingEnabled: false,
    })
  })

  it('ignores blank runtime values instead of clobbering build-time ones', async () => {
    setRuntimeConfig({ supabaseUrl: 'https://build-time.supabase.co' })
    mockFetchOnce({
      ok: true,
      body: { supabase_url: '   ', supabase_anon_key: 'runtime-anon' },
    })

    const config = await loadRuntimeConfig(API_BASE)

    // Blank field falls through to the build-time layer rather than emptying it.
    expect(config.supabaseAnonKey).toBe('runtime-anon')
    expect(config.supabaseUrl).not.toBe('   ')
  })

  it('ignores a non-object payload', async () => {
    mockFetchOnce({ ok: true, body: 'not-an-object' })
    await expect(loadRuntimeConfig(API_BASE)).resolves.toMatchObject({
      pricingEnabled: false,
    })
  })

  it('only treats a real boolean as a feature-flag value', async () => {
    mockFetchOnce({ ok: true, body: { pricing_enabled: 'yes' } })
    const config = await loadRuntimeConfig(API_BASE)
    expect(config.pricingEnabled).toBe(false)
  })

  it('setRuntimeConfig overrides only the provided fields', () => {
    setRuntimeConfig({ turnstileSiteKey: 'test-key' })
    const config = getRuntimeConfig()
    expect(config.turnstileSiteKey).toBe('test-key')
    expect(config.pricingEnabled).toBe(false)
  })
})
