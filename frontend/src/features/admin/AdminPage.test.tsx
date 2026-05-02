import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminPage } from './AdminPage'
import {
  adminGetStats,
  adminListUsers,
  adminSetQuota,
} from '@/lib/api/client'

const translate = (
  key: string,
  maybeDefaultOrOptions?: string | Record<string, unknown>,
  maybeOptions?: Record<string, unknown>,
) => {
  const fallback =
    typeof maybeDefaultOrOptions === 'string' ? maybeDefaultOrOptions : undefined
  const options =
    typeof maybeDefaultOrOptions === 'object' && maybeDefaultOrOptions !== null
      ? maybeDefaultOrOptions
      : maybeOptions
  if (key === 'admin.actions.editQuotaFor' || key === 'admin.actions.saveQuotaFor') {
    return `${key}:${String(options?.name ?? '')}`
  }
  return fallback ?? key
}

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: translate,
    i18n: {
      language: 'en',
      resolvedLanguage: 'en',
    },
  }),
}))

vi.mock('@/hooks/useDocumentTitle', () => ({
  useDocumentTitle: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

vi.mock('@/lib/api/client', () => ({
  adminGetStats: vi.fn(),
  adminListUsers: vi.fn(),
  adminSetQuota: vi.fn(),
}))

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
  })

  it('shows a degraded error instead of the empty state when admin data is unavailable', async () => {
    vi.mocked(adminGetStats).mockRejectedValueOnce(new Error('Admin data unavailable'))
    vi.mocked(adminListUsers).mockRejectedValueOnce(new Error('Admin data unavailable'))

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Admin data unavailable')).toBeInTheDocument()
    })
    expect(screen.queryByText('admin.noUsers')).not.toBeInTheDocument()
  })

  it('keeps the user list visible when stats fail but users still load', async () => {
    vi.mocked(adminGetStats).mockRejectedValueOnce(new Error('Stats unavailable'))
    vi.mocked(adminListUsers).mockResolvedValue({
      items: [
        {
          id: 'user-1',
          display_name: 'Alice',
          avatar_url: '',
          bio: '',
          created_at: new Date().toISOString(),
          plan: 'free',
          usage_count: 2,
          plan_limit: 5,
          role: 'user',
          auth_provider: 'supabase',
        },
      ],
      total: 1,
      has_next: false,
      limit: 25,
      offset: 0,
    })

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Stats unavailable')).toBeInTheDocument()
      expect(screen.getByText('Alice')).toBeInTheDocument()
    })
  })

  it('keeps the displayed plan_limit contract when saving quota overrides', async () => {
    vi.mocked(adminGetStats).mockResolvedValue({
      total_users: 1,
      total_reports: 5,
      active_processing: 0,
      plan_breakdown: { free: 1 },
    })
    vi.mocked(adminListUsers).mockResolvedValue({
      items: [
        {
          id: 'user-1',
          display_name: 'Alice',
          avatar_url: '',
          bio: '',
          created_at: new Date().toISOString(),
          plan: 'free',
          usage_count: 2,
          plan_limit: 5,
          role: 'user',
          auth_provider: 'supabase',
        },
      ],
      total: 1,
      has_next: false,
      limit: 25,
      offset: 0,
    })
    vi.mocked(adminSetQuota).mockResolvedValue({
      id: 'user-1',
      display_name: 'Alice',
      plan: 'free',
      usage_count: 2,
      plan_limit: 8,
      role: 'user',
    })

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Alice')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '5' }))
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '8' } })
    fireEvent.click(screen.getByRole('button', { name: /admin.actions.saveQuotaFor:Alice/i }))

    await waitFor(() => {
      expect(adminSetQuota).toHaveBeenCalledWith('user-1', { plan_limit: 8 })
    })
    expect(screen.getByRole('button', { name: '8' })).toBeInTheDocument()
  })

  it('resyncs the quota editor after external user data changes', async () => {
    vi.mocked(adminGetStats).mockResolvedValue({
      total_users: 1,
      total_reports: 5,
      active_processing: 0,
      plan_breakdown: { free: 1 },
    })
    vi.mocked(adminSetQuota).mockResolvedValue({
      id: 'user-1',
      display_name: 'Alice',
      plan: 'free',
      usage_count: 2,
      plan_limit: 8,
      role: 'user',
    })
    vi.mocked(adminListUsers)
      .mockResolvedValueOnce({
        items: [
          {
            id: 'user-1',
            display_name: 'Alice',
            avatar_url: '',
            bio: '',
            created_at: new Date().toISOString(),
            plan: 'free',
            usage_count: 2,
            plan_limit: 5,
            role: 'user',
            auth_provider: 'supabase',
          },
        ],
        total: 1,
        has_next: false,
        limit: 25,
        offset: 0,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'user-1',
            display_name: 'Alice',
            avatar_url: '',
            bio: '',
            created_at: new Date().toISOString(),
            plan: 'free',
            usage_count: 2,
            plan_limit: 9,
            role: 'user',
            auth_provider: 'supabase',
          },
        ],
        total: 1,
        has_next: false,
        limit: 25,
        offset: 0,
      })

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '5' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '5' }))
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '7' } })
    fireEvent.click(screen.getByRole('button', { name: /admin.actions.saveQuotaFor:Alice/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '8' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByPlaceholderText('Search by name or ID'), {
      target: { value: 'alice' },
    })

    await waitFor(() => {
      expect(adminListUsers).toHaveBeenCalledTimes(2)
    })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '9' })).toBeInTheDocument()
    })
  })

  it('debounces user search and does not reload stats on every keystroke', async () => {
    vi.mocked(adminGetStats).mockResolvedValue({
      total_users: 1,
      total_reports: 5,
      active_processing: 0,
      plan_breakdown: { free: 1 },
    })
    vi.mocked(adminListUsers).mockResolvedValue({
      items: [],
      total: 0,
      has_next: false,
      limit: 25,
      offset: 0,
    })

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(adminGetStats).toHaveBeenCalledTimes(1)
      expect(adminListUsers).toHaveBeenCalledTimes(1)
    })

    const searchInput = await screen.findByPlaceholderText('Search by name or ID')
    fireEvent.change(searchInput, { target: { value: 'a' } })
    fireEvent.change(searchInput, { target: { value: 'ab' } })
    fireEvent.change(searchInput, { target: { value: 'abc' } })

    await new Promise(resolve => window.setTimeout(resolve, 299))
    expect(adminListUsers).toHaveBeenCalledTimes(1)
    expect(adminGetStats).toHaveBeenCalledTimes(1)

    await waitFor(() => {
      expect(adminListUsers).toHaveBeenCalledTimes(2)
    })
    expect(adminGetStats).toHaveBeenCalledTimes(1)
    expect(vi.mocked(adminListUsers).mock.calls[1]?.[0]).toMatchObject({ q: 'abc' })
  })

  it('blocks saving an empty quota value', async () => {
    vi.mocked(adminGetStats).mockResolvedValue({
      total_users: 1,
      total_reports: 5,
      active_processing: 0,
      plan_breakdown: { free: 1 },
    })
    vi.mocked(adminListUsers).mockResolvedValue({
      items: [
        {
          id: 'user-1',
          display_name: 'Alice',
          avatar_url: '',
          bio: '',
          created_at: new Date().toISOString(),
          plan: 'free',
          usage_count: 2,
          plan_limit: 5,
          role: 'user',
          auth_provider: 'supabase',
        },
      ],
      total: 1,
      has_next: false,
      limit: 25,
      offset: 0,
    })

    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '5' })).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '5' }))
    fireEvent.change(screen.getByRole('spinbutton'), { target: { value: '' } })

    const saveButton = screen.getByRole('button', { name: /admin.actions.saveQuotaFor:Alice/i })
    expect(saveButton).toBeDisabled()
    fireEvent.click(saveButton)
    expect(adminSetQuota).not.toHaveBeenCalled()
  })

})
