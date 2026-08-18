/**
 * A 401 used to end the session unconditionally — including transient ones —
 * discarding whatever the user was doing. The backend has always exposed
 * `/auth/refresh` with a grace period; nothing ever called it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const redirects: string[] = []

vi.mock('@/lib/supabase/client', () => ({
  supabase: { auth: { signOut: vi.fn().mockResolvedValue({ error: null }) } },
}))
vi.mock('@/features/history/historyCache', () => ({ clearHistoryCache: vi.fn() }))

import {
  fetchWithTimeout,
  refreshSessionOnce,
  resetSessionRefreshState,
} from '../core'
import { setAccessToken } from '@/lib/auth/token'

function response(status: number, body: unknown = {}): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response
}

beforeEach(() => {
  redirects.length = 0
  resetSessionRefreshState()
  setAccessToken('original-token')
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: {
      href: 'http://localhost/reports/abc',
      pathname: '/reports/abc',
      search: '',
      set hrefSetter(value: string) {
        redirects.push(value)
      },
    },
  })
  // Capture assignments to window.location.href without navigating jsdom.
  let current = 'http://localhost/reports/abc'
  Object.defineProperty(window.location, 'href', {
    configurable: true,
    get: () => current,
    set: (value: string) => {
      current = value
      redirects.push(value)
    },
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  resetSessionRefreshState()
})

describe('401 handling', () => {
  it('renews the session and replays the request', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access_token: 'renewed-token' }))
      .mockResolvedValueOnce(response(200, { ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    const res = await fetchWithTimeout('/api/v1/reports', {}, {}, 1000)

    expect(res.status).toBe(200)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock.mock.calls[1][0]).toContain('/auth/refresh')
    expect(redirects).toEqual([])
  })

  it('ends the session when the refresh itself fails', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(401))
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchWithTimeout('/api/v1/reports', {}, {}, 1000)).rejects.toThrow(
      /Session expired/,
    )
    expect(redirects.at(-1)).toContain('/login?returnTo=')
  })

  it('ends the session when the replay is still unauthorized', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access_token: 'renewed' }))
      .mockResolvedValueOnce(response(401))
    vi.stubGlobal('fetch', fetchMock)

    await expect(fetchWithTimeout('/api/v1/reports', {}, {}, 1000)).rejects.toThrow(
      /Session expired/,
    )
    expect(redirects.at(-1)).toContain('/login?returnTo=')
  })

  it('does not retry when the caller allows unauthorized responses', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(401))
    vi.stubGlobal('fetch', fetchMock)

    const res = await fetchWithTimeout(
      '/api/v1/auth/linuxdo/start',
      {},
      { allowUnauthorized: true },
      1000,
    )

    expect(res.status).toBe(401)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(redirects).toEqual([])
  })

  it('replays with the renewed token, not the stale one', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response(401))
      .mockResolvedValueOnce(response(200, { access_token: 'renewed-token' }))
      .mockResolvedValueOnce(response(200, {}))
    vi.stubGlobal('fetch', fetchMock)

    await fetchWithTimeout(
      '/api/v1/reports',
      { headers: { Authorization: 'Bearer original-token' } },
      {},
      1000,
    )

    const replayHeaders = fetchMock.mock.calls[2][1].headers as Record<string, string>
    expect(replayHeaders.Authorization).toBe('Bearer renewed-token')
  })

  it('collapses concurrent refreshes into a single request', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response(200, { access_token: 'x' }))
    vi.stubGlobal('fetch', fetchMock)

    const [a, b, c] = await Promise.all([
      refreshSessionOnce(),
      refreshSessionOnce(),
      refreshSessionOnce(),
    ])

    expect([a, b, c]).toEqual([true, true, true])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('treats a network failure during refresh as a failed renewal', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(refreshSessionOnce()).resolves.toBe(false)
  })
})
