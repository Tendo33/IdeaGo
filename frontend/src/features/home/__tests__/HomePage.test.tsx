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

vi.mock('@/hooks/useDocumentTitle', () => ({
  useDocumentTitle: vi.fn(),
}))

const HISTORY_CACHE_STORAGE_KEY = 'ideago-history-cache'

describe('HomePage recent reports', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.sessionStorage.clear()
  })

  it('renders cached recent reports immediately', () => {
    window.sessionStorage.setItem(
      HISTORY_CACHE_STORAGE_KEY,
      JSON.stringify({
        pageIndex: 0,
        hasNextPage: false,
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
})
