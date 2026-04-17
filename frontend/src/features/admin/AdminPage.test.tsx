import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminPage } from './AdminPage'
import {
  adminGetStats,
  adminListUsers,
  adminSetQuota,
} from '@/lib/api/client'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, maybeDefaultOrOptions?: string | Record<string, unknown>, maybeOptions?: Record<string, unknown>) => {
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
    },
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

})
