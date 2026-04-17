import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  ApiError,
  startAnalysis,
  getReport,
  getReportWithStatus,
  getReportRuntimeStatus,
  listReports,
  deleteReport,
  cancelAnalysis,
  exportReport,
  getStreamUrl,
  startLinuxDoAuth,
  deleteAccount,
} from '../client'
import { setAccessToken } from '@/lib/auth/token'

const NativeURL = globalThis.URL
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
  localStorage.clear()
  setAccessToken(null)
})

describe('startAnalysis', () => {
  it('sends POST with query and returns report_id', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ report_id: 'abc-123' }),
    })

    const result = await startAnalysis('my startup idea')

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/analyze'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
          'X-Requested-With': 'IdeaGo',
        }),
        body: JSON.stringify({ query: 'my startup idea' }),
      }),
    )
    expect(result).toEqual({ report_id: 'abc-123' })
  })

  it('throws on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 429 })
    await expect(startAnalysis('test')).rejects.toThrow('Analysis failed: 429')
  })

  it('prefers backend error detail when present', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: () => Promise.resolve({ detail: 'Query too short after whitespace normalization' }),
    })

    await expect(startAnalysis('test')).rejects.toThrow(
      'Analysis failed: Query too short after whitespace normalization',
    )
  })
})

describe('getReport', () => {
  it('fetches report by id', async () => {
    const report = { id: 'r1', query: 'test' }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(report),
    })

    const result = await getReport('r1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/r1'),
      expect.objectContaining({ signal: expect.anything() }),
    )
    expect(result).toEqual(report)
  })

  it('throws on 404', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 })
    await expect(getReport('missing')).rejects.toThrow('Report not found: 404')
  })
})

describe('getReportWithStatus', () => {
  it('returns processing on 202', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 202 })
    const result = await getReportWithStatus('pending')
    expect(result).toEqual({ status: 'processing' })
  })

  it('returns ready with report on 200', async () => {
    const report = { id: 'r1', query: 'test' }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(report),
    })
    const result = await getReportWithStatus('r1')
    expect(result).toEqual({ status: 'ready', report })
  })

  it('returns missing on 404', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 })
    const result = await getReportWithStatus('missing')
    expect(result).toEqual({ status: 'missing' })
  })
})

describe('getReportRuntimeStatus', () => {
  it('returns runtime status payload', async () => {
    const payload = {
      status: 'failed',
      report_id: 'r1',
      error_code: 'PIPELINE_FAILURE',
      message: 'Pipeline failed. Please retry.',
      updated_at: '2026-02-28T12:00:00Z',
      query: 'test query',
    }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    })

    const result = await getReportRuntimeStatus('r1')

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/r1/status'),
      expect.objectContaining({ signal: expect.anything() }),
    )
    expect(result).toEqual(payload)
  })
})

describe('listReports', () => {
  it('returns paginated reports', async () => {
    const paginated = {
      items: [{ id: 'r1', query: 'test', created_at: '2026-01-01', competitor_count: 3 }],
      total: null,
      has_next: false,
      limit: 20,
      offset: 0,
    }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(paginated),
    })

    const result = await listReports()
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports'),
      expect.objectContaining({ signal: expect.anything() }),
    )
    expect(result).toEqual(paginated)
  })

  it('supports limit and offset query parameters', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: [], total: null, has_next: false, limit: 5, offset: 20 }),
    })

    await listReports({ limit: 5, offset: 20 })

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/reports\?limit=5&offset=20$/),
      expect.objectContaining({ signal: expect.anything() }),
    )
  })

  it('uses cookie credentials and does not attach legacy bearer token headers', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ items: [], total: null, has_next: false, limit: 5, offset: 0 }),
    })

    await listReports({ limit: 5, offset: 0 })

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/reports\?limit=5&offset=0$/),
      expect.objectContaining({
        credentials: 'include',
        headers: {},
      }),
    )
  })
})

describe('deleteReport', () => {
  it('sends DELETE request', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true })

    await deleteReport('r1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/r1'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('throws on failure', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 500 })
    await expect(deleteReport('r1')).rejects.toThrow('Failed to delete report: 500')
  })
})

describe('cancelAnalysis', () => {
  it('sends DELETE request to cancel endpoint', async () => {
    mockFetch.mockResolvedValueOnce({ ok: true })

    await cancelAnalysis('r1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/r1/cancel'),
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('throws on failure', async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 404 })
    await expect(cancelAnalysis('r1')).rejects.toThrow('Failed to cancel analysis: 404')
  })

  it('uses backend detail on failure when available', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ detail: 'No active analysis found for this report' }),
    })
    await expect(cancelAnalysis('r1')).rejects.toThrow(
      'Failed to cancel analysis: No active analysis found for this report',
    )
  })
})

describe('deleteAccount', () => {
  it('preserves structured failure details from the backend', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: () =>
        Promise.resolve({
          error: {
            code: 'INTERNAL_ERROR',
            message: 'Failed to delete account during billing_cleanup',
            phase: 'billing_cleanup',
            details: ['subscription_cancel_failed'],
            cleanup: {
              domain_data: 'pending',
              billing: 'failed',
              auth_identity: 'pending',
            },
          },
        }),
    })

    await expect(deleteAccount()).rejects.toMatchObject({
      name: 'ApiError',
      message: 'Failed to delete account: Failed to delete account during billing_cleanup',
      statusCode: 500,
      code: 'INTERNAL_ERROR',
      detail: {
        phase: 'billing_cleanup',
        details: ['subscription_cancel_failed'],
        cleanup: {
          domain_data: 'pending',
          billing: 'failed',
          auth_identity: 'pending',
        },
      },
    } satisfies Partial<ApiError>)
  })
})

describe('startLinuxDoAuth', () => {
  it('returns the authorize URL from the backend preflight response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ url: 'https://linux.do/oauth2/authorize?state=test' }),
    })

    const result = await startLinuxDoAuth({
      redirectTo: 'https://ideago.simonsun.cc/auth/callback',
      captchaToken: 'turnstile-token',
    })

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/auth/linuxdo/start'),
      expect.objectContaining({
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'IdeaGo',
        },
        body: JSON.stringify({
          redirect_to: 'https://ideago.simonsun.cc/auth/callback',
          captcha_token: 'turnstile-token',
          prefetch: true,
        }),
        credentials: 'include',
      }),
    )
    expect(result).toBe('https://linux.do/oauth2/authorize?state=test')
  })

  it('surfaces backend error detail when the preflight fails', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      json: () => Promise.resolve({ error: { message: 'Invalid captcha token' } }),
    })

    await expect(
      startLinuxDoAuth({
        redirectTo: 'https://ideago.simonsun.cc/auth/callback',
        captchaToken: 'turnstile-token',
      }),
    ).rejects.toThrow('LinuxDo login failed: Invalid captcha token')
  })
})

describe('URL helpers', () => {
  it('exportReport fetches with auth and triggers download', async () => {
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL: () => 'blob:fake', revokeObjectURL })

    const mockLink = { href: '', download: '', click: vi.fn(), remove: vi.fn() }
    vi.spyOn(document, 'createElement').mockReturnValue(mockLink as unknown as HTMLElement)
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => mockLink as unknown as Node)

    mockFetch.mockResolvedValueOnce({ ok: true, blob: () => Promise.resolve(new Blob(['# Report'])) })
    await exportReport('abc')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/reports/abc/export'),
      expect.objectContaining({ headers: expect.any(Object) }),
    )
    expect(mockLink.click).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake')
  })

  it('getStreamUrl builds correct URL', () => {
    expect(getStreamUrl('abc')).toContain('/api/v1/reports/abc/stream')
  })
})

describe('supabase fallback client', () => {
  it('provides safe auth callbacks when Supabase env is missing', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    vi.resetModules()
    vi.stubEnv('VITE_SUPABASE_URL', '')
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', '')
    vi.stubGlobal('URL', NativeURL)

    try {
      const { supabase } = await import('../../supabase/client')

      await expect(supabase.auth.signOut()).resolves.toEqual({ error: null })
      await expect(supabase.auth.getSession()).resolves.toEqual({
        data: { session: null },
        error: null,
      })

      const authState = supabase.auth.onAuthStateChange(() => {})
      expect(authState.data.subscription.unsubscribe).toEqual(expect.any(Function))

      const oauthResult = await supabase.auth.signInWithOAuth({
        provider: 'google',
      } as never)
      expect(oauthResult.error).toBeInstanceOf(Error)

      const passwordResult = await supabase.auth.signInWithPassword({
        email: 'user@example.com',
        password: 'password',
      })
      expect(passwordResult.error).toBeInstanceOf(Error)

      const signUpResult = await supabase.auth.signUp({
        email: 'user@example.com',
        password: 'password',
      })
      expect(signUpResult.error).toBeInstanceOf(Error)

      const resetResult = await supabase.auth.resetPasswordForEmail('user@example.com')
      expect(resetResult.error).toBeInstanceOf(Error)

      const updateResult = await supabase.auth.updateUser({
        password: 'new-password',
      } as never)
      expect(updateResult.error).toBeInstanceOf(Error)

      expect(warn).toHaveBeenCalledWith(
        'Supabase URL or anon key is missing — auth will not work.',
      )
    } finally {
      warn.mockRestore()
      vi.unstubAllEnvs()
      vi.resetModules()
    }
  })
})
