import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import i18n from '@/lib/i18n/i18n'
import { HomePage } from '@/features/home/HomePage'
import { listReports } from '@/lib/api/client'

vi.mock('@/lib/api/client', () => ({
  isRequestAbortError: vi.fn(() => false),
  listReports: vi.fn(),
}))

vi.mock('@/features/home/components/SearchBox', () => ({
  SearchBox: () => <div>SEARCH_BOX</div>,
}))

let mockUser: { id: string; email: string } | null = { id: 'user-1', email: 'user@example.com' }

vi.mock('@/lib/auth/useAuth', () => ({
  useAuth: () => ({
    user: mockUser,
  }),
}))

vi.mock('@/hooks/useDocumentTitle', () => ({
  useDocumentTitle: vi.fn(),
}))

const HISTORY_CACHE_STORAGE_KEY = 'ideago-history-cache'

describe('HomePage recent reports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
    mockUser = { id: 'user-1', email: 'user@example.com' }
  })

  it('renders cached recent reports immediately', () => {
    window.sessionStorage.setItem(
      HISTORY_CACHE_STORAGE_KEY,
      JSON.stringify({
        userId: 'user-1',
        pageIndex: 0,
        limit: 5,
        hasNextPage: false,
        total: 1,
        reports: [
          {
            id: 'cached-report',
            query: 'Cached home report',
            created_at: new Date().toISOString(),
            competitor_count: 4,
          },
        ],
      }),
    )

    vi.mocked(listReports).mockImplementation(
      () =>
        new Promise(() => {
          // keep pending; initial paint should still use cache
        }),
    )

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.getByText('Cached home report')).toBeInTheDocument()
    expect(screen.queryByText(i18n.t('history.emptyState'))).not.toBeInTheDocument()
  })

  it('does not show the empty state before the recent reports request resolves', () => {
    vi.mocked(listReports).mockImplementation(
      () =>
        new Promise(() => {
          // keep pending to inspect the loading state
        }),
    )

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.queryByText(i18n.t('history.emptyState'))).not.toBeInTheDocument()
    expect(screen.getByLabelText(i18n.t('loading.page'))).toBeInTheDocument()
  })

  it('hydrates cached recent reports after auth bootstrap completes', () => {
    window.sessionStorage.setItem(
      HISTORY_CACHE_STORAGE_KEY,
      JSON.stringify({
        userId: 'user-1',
        pageIndex: 0,
        limit: 5,
        hasNextPage: false,
        total: 1,
        reports: [
          {
            id: 'cached-report',
            query: 'Hydrated cached report',
            created_at: new Date().toISOString(),
            competitor_count: 4,
          },
        ],
      }),
    )
    mockUser = null

    vi.mocked(listReports).mockImplementation(
      () =>
        new Promise(() => {
          // keep pending; hydration should come from cache after rerender
        }),
    )

    const { rerender } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.queryByText('Hydrated cached report')).not.toBeInTheDocument()

    mockUser = { id: 'user-1', email: 'user@example.com' }
    rerender(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.getByText('Hydrated cached report')).toBeInTheDocument()
  })

  it('clips oversized shared cache to the recent reports limit', () => {
    window.sessionStorage.setItem(
      HISTORY_CACHE_STORAGE_KEY,
      JSON.stringify({
        userId: 'user-1',
        pageIndex: 0,
        limit: 20,
        hasNextPage: false,
        total: 20,
        reports: Array.from({ length: 20 }, (_, index) => ({
          id: `report-${index + 1}`,
          query: `Shared cached report ${index + 1}`,
          created_at: new Date().toISOString(),
          competitor_count: index + 1,
        })),
      }),
    )

    vi.mocked(listReports).mockImplementation(() => new Promise(() => {}))

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    )

    expect(screen.queryByText('Shared cached report 1')).not.toBeInTheDocument()
    expect(screen.getByLabelText(/loading page content/i)).toBeInTheDocument()
  })
})
