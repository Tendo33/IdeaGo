import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ProfilePage } from './ProfilePage'
import { deleteAccount, getMyProfile, getQuotaInfo, isApiError } from '@/lib/api/client'

const mockSignOut = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string, fallback?: string) => fallback ?? key,
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

vi.mock('@/lib/auth/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: 'user-1',
      email: 'alice@example.com',
      display_name: 'Alice',
    },
    signOut: mockSignOut,
    patchUser: vi.fn(),
  }),
}))

vi.mock('@/lib/auth/AuthContext', () => ({
  getUserDisplayName: () => 'Alice',
  truncateMiddle: (value: string) => value,
}))

vi.mock('@/lib/api/client', () => ({
  getMyProfile: vi.fn(),
  getQuotaInfo: vi.fn(),
  updateMyProfile: vi.fn(),
  deleteAccount: vi.fn(),
  isApiError: vi.fn(() => false),
}))

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSignOut.mockReset()
    vi.mocked(getMyProfile).mockResolvedValue({
      display_name: 'Alice',
      avatar_url: '',
      bio: 'builder',
      created_at: new Date().toISOString(),
      role: 'user',
    })
  })

  it('shows a quota unavailable warning and hides the usage meter when quota loading fails', async () => {
    vi.mocked(getQuotaInfo).mockRejectedValueOnce(new Error('Quota temporarily unavailable'))

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Quota temporarily unavailable')).toBeInTheDocument()
    })
    expect(screen.queryByText('Quota usage')).not.toBeInTheDocument()
  })

  it('renders quota usage details when quota loads successfully', async () => {
    vi.mocked(getQuotaInfo).mockResolvedValue({
      usage_count: 2,
      plan_limit: 5,
      plan: 'daily',
      reset_at: new Date().toISOString(),
    })

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('2 / 5')).toBeInTheDocument()
    })
    expect(screen.getByText('Quota usage')).toBeInTheDocument()
  })

  it('shows a stuck deletion warning when account deletion leaves the account marked for deletion', async () => {
    vi.mocked(getQuotaInfo).mockResolvedValue({
      usage_count: 2,
      plan_limit: 5,
      plan: 'daily',
      reset_at: new Date().toISOString(),
    })
    vi.mocked(isApiError).mockReturnValue(true)
    vi.mocked(deleteAccount).mockRejectedValue({
      detail: {
        phase: 'billing_cleanup',
        cleanup: {
          profile: 'rollback_failed',
        },
      },
    })

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Delete Account')).toBeInTheDocument()
    })

    fireEvent.click(screen.getAllByText('Delete Account')[0]!)
    fireEvent.click(screen.getByText('Yes, Delete Everything'))

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalledTimes(1)
    })
  })

  it('shows a partial recovery warning when account access is restored after some data was removed', async () => {
    vi.mocked(getQuotaInfo).mockResolvedValue({
      usage_count: 2,
      plan_limit: 5,
      plan: 'daily',
      reset_at: new Date().toISOString(),
    })
    vi.mocked(isApiError).mockReturnValue(true)
    vi.mocked(deleteAccount).mockRejectedValue({
      detail: {
        phase: 'domain_data_cleanup',
        cleanup: {
          profile: 'restored_access_only',
        },
      },
    })

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Delete Account')).toBeInTheDocument()
    })

    fireEvent.click(screen.getAllByText('Delete Account')[0]!)
    fireEvent.click(screen.getByText('Yes, Delete Everything'))

    await waitFor(() => {
      expect(mockSignOut).toHaveBeenCalledTimes(1)
    })
  })

  it('keeps the user signed in for recoverable delete failures', async () => {
    vi.mocked(getQuotaInfo).mockResolvedValue({
      usage_count: 2,
      plan_limit: 5,
      plan: 'daily',
      reset_at: new Date().toISOString(),
    })
    vi.mocked(isApiError).mockReturnValue(true)
    vi.mocked(deleteAccount).mockRejectedValue({
      detail: {
        phase: 'billing_cleanup',
        cleanup: {
          billing: 'failed',
        },
      },
    })

    render(
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Delete Account')).toBeInTheDocument()
    })

    fireEvent.click(screen.getAllByText('Delete Account')[0]!)
    fireEvent.click(screen.getByText('Yes, Delete Everything'))

    await waitFor(() => {
      expect(
        screen.getByText(
          'Billing cleanup failed. Subscription or customer cleanup needs attention.',
        ),
      ).toBeInTheDocument()
    })
    expect(mockSignOut).not.toHaveBeenCalled()
  })
})
